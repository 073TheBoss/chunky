# coding=utf-8
# Releasebot Copyright (c) 2013 Jesper �qvist <jesper@llbit.se>
# requires PRAW, Launchpadlib
import sys
import praw
import re
import io
import traceback
from subprocess import call
from getpass import getpass
from datetime import datetime
from string import join
from launchpadlib.launchpad import Launchpad

class Version:
	regex = re.compile('^(\d+\.\d+\.\d+)-?([a-zA-Z]*\.?\d*)$')
	full = ''
	milestone = ''
	suffix = ''
	series = ''
	rc = ''
	changelog = ''
	release_notes = ''
	
	def __init__(self, version):
		self.full = version
		regex = re.compile('^(\d+\.\d+\.\d+)-?([a-zA-Z]*\.?\d*)$')
		r = regex.match(version)
		assert r, "Invalid version name: %s (expected e.g. 1.2.13-rc.1)" % version
		self.milestone = r.groups()[0]
		self.suffix = r.groups()[1]
		self.series = join(self.milestone.split('.')[:2], '.')
		if self.suffix.startswith('rc.'):
			self.rc = self.suffix[3:]
		else:
			self.release_notes = open("release_notes-%s.txt" % self.milestone, 'r').read()

		# load changelog
		lines = open('ChangeLog.txt', 'r').readlines().__iter__()
		while True:
			next = lines.next()
			if not next or next.startswith(self.milestone):
				break
		for line in lines:
			if not line or not line.strip():
				break
			else:
				self.changelog += line

def publish(version):
	should_build = raw_input('Build release? [y/n] ')
	if should_build == "y":
		if call(['cmd', '/c', 'ant', '-Dversion=' + version.full, 'release']) is not 0:
			print "Error: Ant build failed!"
			sys.exit(1)
		if call(['makensis', 'Chunky.nsi']) is not 0:
			print "Error: NSIS failed!"
			sys.exit(1)
	should_publish = raw_input('Publish files? [y/n] ')
	if should_publish == "y":
		if version.rc:
			zip_url = publish_rc()
			post_rc_thread(version, zip_url)
		else:
			(new_release, exe_url, zip_url) = publish_release(version)
			post_release_thread(version, exe_url, zip_url)
		
def publish_rc():
	# TODO automatic dropbox or FTP upload
	return raw_input('Release candidate zip file URL: ')

def post_rc_thread(version, zip_url):
	should_post = raw_input('Post RC thread? [y/n] ')
	if should_post != "y":
		return
	r = praw.Reddit(user_agent='releasebot')
	pw = getpass(prompt='releasebot login: ')
	r.login('releasebot', pw)
	post = r.submit('chunky', 'Chunky %s Release Candidate %s' % (version.full, version.rc),
		text=(
('''Release candidates are a way of letting experienced users try out a new
version before it is officially released in order to provide feedback. The
goal is to improve the quality of the official releases. If you are at all
unsure of what you are doing please wait for the proper release.

If you decide to try this release candidate and find a bug, please report it
in this thread or over at [the GitHub issue tracker](https://github.com/llbit/chunky/issues).

* ** Please back up your renders before using this software! **
* Always read the change log before running a release candidate!

[Download link.](%s)

###ChangeLog

''' % zip_url) + version.changelog))
	post.set_flair('announcement', 'announcement')
	print "Submitted Reddit release thread!"

def lp_upload_file(version, release, filename, description, content_type, file_type):
	# TODO handle re-uploads
	FILE_TYPES = dict(
		tarball='Code Release Tarball',
		readme='README File',
		release_notes='Release Notes',
		changelog='ChangeLog File',
		installer='Installer file')
	print "Uploading %s..." % filename
	try:
		release_file = release.add_file(
			filename=filename,
			description=description,
			file_content=open('build/' + filename, 'rb').read(),
			content_type=content_type,
			file_type=FILE_TYPES[file_type])
		return 'https://launchpad.net/chunky/%s/%s/+download/%s' \
			% (version.series, version.milestone, filename)
	except:
		exc_type, exc_value, exc_traceback = sys.exc_info()
		print "File upload error:"
		traceback.print_exception(exc_type, exc_value, exc_traceback)
		return None

def publish_release(version):
	launchpad = Launchpad.login_with('Releasebot', 'production', 'lpcache')

	chunky = launchpad.projects['chunky']

	# check if release exists
	release = None
	for r in chunky.releases:
		if r.version == version.milestone:
			release = r
			print "Previous %s release found: proceeding to upload additional files." \
				% version.milestone
			break

	is_new_release = release is None
			
	if release is None:
		# check if milestone exists
		milestone = None
		for ms in chunky.all_milestones:
			if ms.name == version.milestone:
				milestone = ms
				break

		# create milestone (and series) if needed
		if milestone is None:
			series = None
			for s in chunky.series:
				if s.name == version.series:
					series = s
					break
			if series is None:
				series = chunky.newSeries(
					name=version.series,
					summary="The current stable series for Chunky. NB: The code is maintained separately on GitHub.")
				print "Series %s created. Please manually update the series summary:" % version.series
				print series

			milestone = series.newMilestone(name=version.milestone)
			print "Milestone %s created." % version.milestone

		# create release
		print "TODO: include proper changelog and release notes"
		release = milestone.createProductRelease(
			release_notes=version.release_notes,
			changelog=version.changelog,
			date_released=datetime.today())
		milestone.is_active = False
		print "Release %s created" % version.milestone

	assert release is not None

	# upload release files
	tarball_url = lp_upload_file(
		version,
		release,
		'chunky-%s.tar.gz' % version.full,
		'Source Code',
		'application/x-tar',
		'tarball')
	assert tarball_url
	print tarball_url
	zip_url = lp_upload_file(
		version,
		release,
		'Chunky-%s.zip' % version.full,
		'Binaries',
		'application/zip',
		'installer')
	assert zip_url
	print zip_url
	exe_url = lp_upload_file(
		version,
		release,
		'Chunky-%s.exe' % version.full,
		'Windows Installer',
		'application/octet-stream',
		'installer')
	assert exe_url
	print exe_url
	return (is_new_release, exe_url, zip_url)

"post a reddit release thread"
def post_release_thread(version, exe_url, zip_url):
	should_post = raw_input('Post release thread? [y/n] ')
	if should_post != "y":
		return
	r = praw.Reddit(user_agent='releasebot')
	pw = getpass(prompt='releasebot login: ')
	r.login('releasebot', pw)
	post = r.submit('chunky', 'Version %s released!' % version.full,
		text=('''###Downloads

* [Windows installer](%s)
* [Cross-platform binaries](%s)

###Release Notes

''' % (exe_url, zip_url)) + version.release_notes + '''

###ChangeLog

''' + version.changelog)
	post.set_flair('announcement', 'announcement')
	print "Submitted Reddit release thread!"

version = Version(raw_input('Enter version: '))
print "Releasebot is now publishing Chunky " + version.full
try:
	publish(version)
	should_push = raw_input('All done. Push git changes? [y/n] ')
	if should_push == "y":
		call(['git', 'push', 'origin', 'master'])# push version bump commit
		call(['git', 'push', 'origin', version.full])# push version tag
except:
	exc_type, exc_value, exc_traceback = sys.exc_info()
	print "Unexpected error:"
	traceback.print_exception(exc_type, exc_value, exc_traceback)
	print "Release aborted."
	raw_input()
