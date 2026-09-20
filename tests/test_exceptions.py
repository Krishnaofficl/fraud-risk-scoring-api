from app.core.exceptions import (
    AppException,
    DatabaseUnavailableException,
    ModelNotLoadedException,
    EntityNotFoundException,
    AuthenticationFailedException,
    AuthorizationFailedException,
    ConflictException,
)


def test_custom_domain_exceptions():
    db_exc = DatabaseUnavailableException(detail={"connection": "refused"})
    assert db_exc.status_code == 503
    assert db_exc.error_code == "DATABASE_UNAVAILABLE"
    assert "Database service" in db_exc.message
    assert db_exc.detail == {"connection": "refused"}

    model_exc = ModelNotLoadedException()
    assert model_exc.status_code == 503
    assert model_exc.error_code == "MODEL_UNAVAILABLE"

    not_found_exc = EntityNotFoundException(message="User not found")
    assert not_found_exc.status_code == 404
    assert not_found_exc.error_code == "ENTITY_NOT_FOUND"
    assert not_found_exc.message == "User not found"

    auth_exc = AuthenticationFailedException()
    assert auth_exc.status_code == 401
    assert auth_exc.error_code == "AUTHENTICATION_FAILED"

    authz_exc = AuthorizationFailedException()
    assert authz_exc.status_code == 403
    assert authz_exc.error_code == "AUTHORIZATION_FAILED"

    conflict_exc = ConflictException(message="Email already taken")
    assert conflict_exc.status_code == 409
    assert conflict_exc.error_code == "RESOURCE_CONFLICT"
    assert conflict_exc.message == "Email already taken"
