from lucidnews.mcp.errors import LucidNewsMcpError


def test_lucidnews_mcp_error_string_representation() -> None:
    err = LucidNewsMcpError(code="E_TEST", message="boom", details={"k": "v"})

    assert str(err) == "E_TEST: boom"
    assert err.details == {"k": "v"}
