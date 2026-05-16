import keyring
from keyring.errors import KeyringError, NoKeyringError

SERVICE_NAME = "DB Explorer"
REFERENCE_PREFIX = "keyring:db-explorer:"
PASSWORD_FIELD = "password"


class CredentialVaultError(RuntimeError):
    pass


def make_password_reference(connection_id):
    if connection_id is None:
        raise CredentialVaultError("Connection id is required to store a password securely.")
    return f"{REFERENCE_PREFIX}connection:{connection_id}:{PASSWORD_FIELD}"


def is_password_reference(value):
    return isinstance(value, str) and value.startswith(REFERENCE_PREFIX)


def save_password(reference, password):
    if not reference:
        raise CredentialVaultError("Credential reference is required.")
    if password is None:
        password = ""
    try:
        keyring.set_password(SERVICE_NAME, reference, password)
    except (KeyringError, NoKeyringError) as exc:
        raise CredentialVaultError("Secure credential storage is unavailable on this system.") from exc


def load_password(reference):
    if not reference:
        return reference
    if not is_password_reference(reference):
        return reference
    try:
        password = keyring.get_password(SERVICE_NAME, reference)
    except (KeyringError, NoKeyringError) as exc:
        raise CredentialVaultError("Secure credential storage is unavailable on this system.") from exc
    return password or ""


def delete_password(reference):
    if not is_password_reference(reference):
        return
    try:
        keyring.delete_password(SERVICE_NAME, reference)
    except keyring.errors.PasswordDeleteError:
        return
    except (KeyringError, NoKeyringError) as exc:
        raise CredentialVaultError("Secure credential storage is unavailable on this system.") from exc


def resolve_password(value):
    if is_password_reference(value):
        return load_password(value)
    return value


def store_password_for_connection(connection_id, password):
    if password is None or password == "":
        return password
    if is_password_reference(password):
        return password
    reference = make_password_reference(connection_id)
    save_password(reference, password)
    return reference
