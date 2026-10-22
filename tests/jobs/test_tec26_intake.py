"""Regression probes for the job-specific native reader (synthetic Max stub)."""
import ast
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[2] / 'jobs/TEC26-OKS/scripts/read_max.py'

def test_bitmap_is_not_queried_as_material():
    tree = ast.parse(SCRIPT.read_text(encoding='utf-8'))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'material')
    bitmap = SimpleNamespace(name='Map #1')
    def reject(_):
        raise RuntimeError('Unable to convert: Map #1:Bitmap to type: Material')
    rt = SimpleNamespace(getHandleByAnim=lambda _: 1, classOf=lambda _: 'Bitmaptexture',
        superClassOf=lambda _: 'textureMap', getPropNames=lambda _: [],
        getNumSubTexmaps=lambda _: 0, getNumSubMtls=reject)
    scope = {'rt': rt}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SCRIPT), 'exec'), scope)
    assert scope['material'](bitmap)['submaterials'] == []
