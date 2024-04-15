from textwrap import dedent

from bumpsemver.files.tomlpath import TomlPath


def test_simplest_query_int():
    obj = TomlPath.query("a = 1", "a")
    assert obj == 1


def test_simplest_query_string():
    obj = TomlPath.query('a = "foobar"', "a")
    assert obj == "foobar"


def test_simplest_query_float():
    obj = TomlPath.query("a = 1.2", "a")
    assert obj == 1.2


def test_simplest_query_boolean_pos():
    obj = TomlPath.query("a = true", "a")
    assert obj is True

    obj = TomlPath.query("a = false", "a")
    assert obj is False


#
# def test_simplest_query_boolean_neg():
#     obj = TomlPath.retrieve("a = True", "a")
#     assert obj == "True"
#
#     obj = TomlPath.retrieve("a = False", "a")
#     assert obj == "False"


def test_simplest_query_array():
    obj = TomlPath.query("a = [1, 2, 3]", "a")
    assert obj == [1, 2, 3]


def test_query_array_element():
    obj = TomlPath.query(
        dedent(
            """
    [[a]]
    name = "e1"
    value = [ 1, 2 ]

    [[a]]
    name = "e2"
    value = [ 3, 4 ]
    """
        ).strip(),
        "a[1].value[1]",
    )
    assert obj == 4


def test_query_array_all_elements():
    toml = dedent(
        """
    [[a]]
    name = "e1"
    value = [ 1, 2 ]

    [[a]]
    name = "e2"
    value = [ 3, 4 ]
    """
    ).strip()

    obj = TomlPath.query(toml, "a[1].value[]")
    assert obj == [3, 4]

    obj = TomlPath.query(toml, "a[1].value")
    assert obj == [3, 4]

    obj = TomlPath.query(toml, "a[].value[1]")
    assert obj == [2, 4]

    obj = TomlPath.query(toml, "a.value[1]")
    assert obj == [2, 4]

    obj = TomlPath.query(toml, "a.name")
    assert obj == ["e1", "e2"]

    obj = TomlPath.query(toml, "a[].value[]")
    assert obj == [[1, 2], [3, 4]]

    obj = TomlPath.query(toml, "a.value[]")
    assert obj == [[1, 2], [3, 4]]

    obj = TomlPath.query(toml, "a.value")
    assert obj == [[1, 2], [3, 4]]


def test_simplest_update_int():
    result = TomlPath.update("a = 1", "a", 2)
    assert result == "a = 2"


def test_simplest_update_string():
    result = TomlPath.update('a = "foobar"', "a", "barfoo")
    assert result == 'a = "barfoo"'


def test_simplest_update_float():
    result = TomlPath.update("a = 1.2", "a", 2.5)
    assert result == "a = 2.5"


def test_simplest_update_boolean():
    result = TomlPath.update("a = true", "a", False)
    assert result == "a = false"

    result = TomlPath.update("a = false", "a", True)
    assert result == "a = true"

    result = TomlPath.update("a = false", "a", False)
    assert result == "a = false"


def test_simplest_update_array():
    result = TomlPath.update("a = [1, 2, 3]", "a", [4, 5])
    assert result == "a = [4, 5]"


def test_update_array_element():
    result = TomlPath.update(
        dedent(
            """
    [[a]]
    name = "e1"
    value = [ 1, 2 ]

    [[a]]
    name = "e2"
    value = [ 3, 4 ]
    """
        ).strip(),
        "a[1].value[1]",
        5,
    )

    expected = dedent(
        """[[a]]
name = "e1"
value = [ 1, 2 ]

[[a]]
name = "e2"
value = [ 3, 5 ]
"""
    ).strip()
    assert result == expected


def test_update_array_all_elements():
    orig = dedent(
        """
    [[a]]
    name = "e1"
    value = [ 1, 2 ]

    [[a]]
    name = "e2"
    value = [ 3, 4 ]
    """
    ).strip()

    expected = dedent(
        """[[a]]
name = "e1"
value = [ 1, 6 ]

[[a]]
name = "e2"
value = [ 3, 6 ]
"""
    ).strip()

    result = TomlPath.update(orig, "a[].value[1]", 6)
    assert result == expected

    result = TomlPath.update(orig, "a.value[1]", 6)
    assert result == expected

    expected = dedent(
        """[[a]]
name = "e1"
value = 7

[[a]]
name = "e2"
value = 7
"""
    ).strip()

    result = TomlPath.update(orig, "a[].value[]", 7)
    assert result == expected

    result = TomlPath.update(orig, "a[].value", 7)
    assert result == expected

    result = TomlPath.update(orig, "a.value[]", 7)
    assert result == expected

    result = TomlPath.update(orig, "a.value", 7)
    assert result == expected

    expected = dedent(
        """[[a]]
name = "e1"
value = [ 1, 2 ]

[[a]]
name = "e2"
value = 8
"""
    ).strip()

    result = TomlPath.update(orig, "a[1].value", 8)
    assert result == expected

    result = TomlPath.update(orig, "a[1].value[]", 8)
    assert result == expected


def test_update_objects_array():
    orig = dedent(
        """
    [[dummy]]
    [[dummy.a]]
    name = "object1_1"
    version = 1

    [[dummy.a]]
    name = "object1_2"
    version = 2

    [[dummy]]
    [[dummy.a]]
    name = "object2_1"
    version = 3

    [[dummy.a]]
    name = "object2_2"
    version = 4

    [[dummy.a]]
    name = "object2_3"
    version = 5
    """
    ).strip()

    expected = dedent(
        """[[dummy]]
[[dummy.a]]
name = "object1_1"
version = 9

[[dummy.a]]
name = "object1_2"
version = 9

[[dummy]]
[[dummy.a]]
name = "object2_1"
version = 9

[[dummy.a]]
name = "object2_2"
version = 9

[[dummy.a]]
name = "object2_3"
version = 9
    """
    ).strip()

    result = TomlPath.update(orig, "dummy.a.version", 9)
    assert result == expected


def test_update_preserving_comments():
    orig = dedent(
        """
    # comment 1
    [[dummy]] # comment 2
    # comment 3
    [[dummy.a]]
    name = "object1_1" # comment 4
    version = 1 # comment 5
    # comment 6
    [[dummy.a]] # comment 7
    # comment 8
    name = "object1_2"  # comment 9
    version = 2  # comment 10
    # comment 11
    [[dummy]]  # comment 12
    #    comment 13
    [[dummy.a]]      #    comment 14
    #############################################
    name = "object2_1" #comment 15
    # comment 16
    version = 3
    # comment 17

    [[dummy.a]]    # comment 18
    name = "object2_2" #      comment 19
    # # # # comment 20
    version = 4 # # comment 11

    [[dummy.a]]
    name = "object2_3"
    version = 5
    """
    ).strip()

    expected = dedent(
        """# comment 1
[[dummy]] # comment 2
# comment 3
[[dummy.a]]
name = "object1_1" # comment 4
version = 10 # comment 5
# comment 6
[[dummy.a]] # comment 7
# comment 8
name = "object1_2"  # comment 9
version = 10  # comment 10
# comment 11
[[dummy]]  # comment 12
#    comment 13
[[dummy.a]]      #    comment 14
#############################################
name = "object2_1" #comment 15
# comment 16
version = 10
# comment 17

[[dummy.a]]    # comment 18
name = "object2_2" #      comment 19
# # # # comment 20
version = 10 # # comment 11

[[dummy.a]]
name = "object2_3"
version = 10
    """
    ).strip()

    result = TomlPath.update(orig, "dummy.a.version", 10)
    assert result == expected
