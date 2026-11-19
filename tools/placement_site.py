"""Import shim (#1407): the site placement scene helpers moved to ``dt_ai.placement.scene``.

Pattern: n/a | new-case: module alias, no code. ``from tools import placement_site as ps`` returns the same module
object as ``dt_ai.placement.scene`` (one owner, private names and monkeypatching included).
"""
import sys

from dt_ai.placement import scene as _scene

sys.modules[__name__] = _scene
