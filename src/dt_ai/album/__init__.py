"""Album reader (#317) - RED stub: tests first, implementation in the next commit."""


class AlbumReadError(ValueError):
    reason = "not_implemented"


class AlbumExtraMissing(RuntimeError):
    pass


def _todo(*_a, **_k):
    raise NotImplementedError("album reader not implemented yet (#317)")


read_page = reading_to_json = check_dimension = check_level_pair = parse_level_text = _todo
