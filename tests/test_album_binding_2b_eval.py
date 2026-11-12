"""new-case: one-to-one real DWG dimension-oracle controls for PDF binding #1254."""
import pytest

from tools.research.pdf_album.binding_2b_eval import score_dimensions


def prediction(value=2000, axes=('1','2'), kind='axis_pair'):
    return {'kind':'dimension','value':value,'binding':{'type':kind,'axes':list(axes)}}


def test_dimension_oracle_one_to_one():
    truth=[{'handle':'A','value_mm':2000,'axes':['1','2']}]
    assert score_dimensions([prediction()],truth)=={'found':1,'correct':1,'wrong':0,'missed':0,'truth':1,'precision':1.0,'recall':1.0}
    r=score_dimensions([prediction(),prediction()],truth)
    assert (r['correct'],r['wrong'],r['missed'])==(1,1,0)


@pytest.mark.parametrize('value,axes', [(2001,('1','2')),(2000,('1','3')),(float('nan'),('1','2')),(float('inf'),('1','2'))])
def test_dimension_oracle_rejects_wrong_or_nonfinite(value,axes):
    r=score_dimensions([prediction(value,axes)],[{'handle':'A','value_mm':2000,'axes':['1','2']}])
    assert (r['correct'],r['wrong'],r['missed'])==(0,1,1)


def test_empty_oracle_is_unknown_not_perfect():
    r=score_dimensions([],[])
    assert r['precision'] is None and r['recall'] is None


def test_unbound_and_other_classes_do_not_claim_semantic_recall():
    r=score_dimensions([prediction(kind='unbound')],[{'handle':'A','value_mm':2000,'axes':['1','2']}])
    assert r['found']==0 and r['missed']==1


def test_duplicate_oracle_handle_is_error():
    with pytest.raises(ValueError,match='duplicate'):
        score_dimensions([],[{'handle':'A'},{'handle':'A'}])
