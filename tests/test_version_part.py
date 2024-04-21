from bumpsemver.version_part import NumericVersionPartConfiguration, VersionPart, Version, VersionConfig

vpc = NumericVersionPartConfiguration()


def test_version_part_init():
    assert VersionPart(vpc.first_value, vpc).value == vpc.first_value


def test_version_part_copy():
    vp = VersionPart(vpc.first_value, vpc)
    vc = vp.copy()
    assert vp.value == vc.value
    assert id(vp) != id(vc)


def test_version_part_bump():
    vp = VersionPart(vpc.first_value, vpc)
    vc = vp.bump()
    assert vc.value == vpc.bump(vpc.first_value)


def test_version_part_format():
    assert f"{VersionPart(vpc.first_value, vpc)}" == vpc.first_value


def test_version_part_equality():
    assert VersionPart(vpc.first_value, vpc) == VersionPart(vpc.first_value, vpc)


def test_version_part_null():
    assert VersionPart(vpc.first_value, vpc).null() == VersionPart(vpc.first_value, vpc)


def test_version_part_repr():
    assert (
        repr(VersionPart(vpc.first_value, vpc))
        == f"<bumpsemver.VersionPart:NumericVersionPartConfiguration:{vpc.first_value}>"
    )


def test_version_repr():
    vc = VersionConfig()
    version = vc.parse("1.2.3")
    assert repr(version) == "<bumpsemver.Version:major=1, minor=2, patch=3>"
