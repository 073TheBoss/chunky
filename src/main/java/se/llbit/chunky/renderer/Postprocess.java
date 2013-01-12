package se.llbit.chunky.renderer;

import se.llbit.nbt.AnyTag;

/**
 * Postprocessing modes
 * @author Jesper Öqvist <jesper@llbit.se>
 */
@SuppressWarnings("javadoc")
public enum Postprocess {
	// default (index 0)
	GAMMA {
		@Override
		public String toString() {
			return "Gamma correction";
		}
	},
	NONE {
		@Override
		public String toString() {
			return "None";
		}
	},
	TONEMAP1 {
		@Override
		public String toString() {
			return "Tonemap op1";
		}
	};
	
	public static final Postprocess[] values = values();

	public static Postprocess get(int index) {
		index = Math.max(0, index);
		index = Math.min(values.length-1, index);
		return values[index];
	}
	
	public static Postprocess get(AnyTag tag) {
		return get(tag.intValue());
	}
}
