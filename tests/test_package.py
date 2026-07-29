import hokum


def test_package_is_importable():
    # Setup — nothing to arrange for a bare import check.

    # Exercise
    module_name = hokum.__name__

    # Verify
    assert module_name == "hokum"
