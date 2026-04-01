from wildcat._utils import _args


class TestCollect:
    def test(_):

        def example(here, are, some, parameters, in_a, function):
            pass

        example(1, 2, 3, 4, 5, 6)
        output = _args.collect(example)
        assert output == ["here", "are", "some", "parameters", "in_a", "function"]
