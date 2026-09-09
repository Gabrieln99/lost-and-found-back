from eth_account import Account
from eth_account.messages import encode_defunct

from app.signing import (
    SignatureError,
    build_read_signable_message,
    build_signable_message,
    is_timestamp_fresh,
    recover_signer,
)


def sign_text(text: str, private_key) -> str:
    signed = Account.sign_message(encode_defunct(text=text), private_key=private_key)
    sig_hex = signed.signature.hex()
    return sig_hex if sig_hex.startswith("0x") else f"0x{sig_hex}"


def test_build_signable_message_is_deterministic():
    a = build_signable_message(3, 1_700_000_000, "hello")
    b = build_signable_message(3, 1_700_000_000, "hello")
    assert a == b


def test_build_signable_message_includes_all_three_inputs():
    message = build_signable_message(3, 1_700_000_000, "hello")
    assert "3" in message
    assert "1700000000" in message
    assert "hello" in message


def test_build_signable_message_differs_for_different_listings():
    a = build_signable_message(3, 1_700_000_000, "hello")
    b = build_signable_message(4, 1_700_000_000, "hello")
    assert a != b


def test_read_and_write_signable_messages_never_collide():
    # Domain separation: a signature authorizing a read must never also
    # verify as a valid write signature (or vice versa), even for the
    # "same" listing_id/timestamp.
    write_message = build_signable_message(3, 1_700_000_000, "")
    read_message = build_read_signable_message(3, 1_700_000_000)
    assert write_message != read_message


class TestRecoverSigner:
    def test_recovers_the_actual_signer(self):
        account = Account.create()
        message = build_signable_message(3, 1_700_000_000, "Meet at the fountain at noon")
        signature = sign_text(message, account.key)

        recovered = recover_signer(message, signature)

        assert recovered.lower() == account.address.lower()

    def test_a_different_signer_recovers_to_a_different_address(self):
        signer = Account.create()
        impostor = Account.create()
        message = build_signable_message(3, 1_700_000_000, "hello")
        signature = sign_text(message, impostor.key)

        recovered = recover_signer(message, signature)

        assert recovered.lower() != signer.address.lower()

    def test_tampering_with_the_message_after_signing_recovers_a_different_address(self):
        account = Account.create()
        original = build_signable_message(3, 1_700_000_000, "original body")
        tampered = build_signable_message(3, 1_700_000_000, "tampered body")
        signature = sign_text(original, account.key)

        recovered = recover_signer(tampered, signature)

        # Not a SignatureError -- ECDSA recovery always succeeds
        # structurally for a well-formed signature. The security property
        # is that it recovers to the wrong address, which the caller (the
        # owner/finder authorization check) then rejects.
        assert recovered.lower() != account.address.lower()

    def test_raises_signature_error_for_a_malformed_signature(self):
        message = build_signable_message(3, 1_700_000_000, "hello")

        try:
            recover_signer(message, "not-a-signature")
            raise AssertionError("expected SignatureError")
        except SignatureError:
            pass

    def test_raises_signature_error_for_an_empty_signature(self):
        message = build_signable_message(3, 1_700_000_000, "hello")

        try:
            recover_signer(message, "")
            raise AssertionError("expected SignatureError")
        except SignatureError:
            pass


class TestIsTimestampFresh:
    def test_current_timestamp_is_fresh(self):
        now = 1_700_000_000.0
        assert is_timestamp_fresh(1_700_000_000, now=now) is True

    def test_timestamp_within_tolerance_is_fresh(self):
        now = 1_700_000_000.0
        assert is_timestamp_fresh(1_700_000_000 - 299, now=now) is True
        assert is_timestamp_fresh(1_700_000_000 + 299, now=now) is True

    def test_timestamp_outside_tolerance_is_not_fresh(self):
        now = 1_700_000_000.0
        assert is_timestamp_fresh(1_700_000_000 - 301, now=now) is False
        assert is_timestamp_fresh(1_700_000_000 + 301, now=now) is False
