"""Save the currently loaded startup scene as a .blend file (headless).

Usage:
  blender -b --app-template Z-Anatomy --python tools/blender/save_template.py -- C:\\path\\Z-Anatomy.blend

Used to turn the Z-Anatomy application template into a plain .blend without opening the GUI.
"""
import sys

import bpy

out = sys.argv[sys.argv.index("--") + 1]
n = len(bpy.data.objects)
print("Objects in scene:", n)
if n < 100:
    sys.exit("Only %d objects loaded: the template startup file was not used. Save from the GUI instead." % n)
bpy.ops.wm.save_as_mainfile(filepath=out)
print("Saved", out)
