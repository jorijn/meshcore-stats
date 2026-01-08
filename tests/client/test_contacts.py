"""Tests for contact lookup functions."""

from types import SimpleNamespace
from unittest.mock import MagicMock


class TestGetContactByName:
    """Tests for get_contact_by_name function."""

    def test_returns_contact_when_found(self, mock_meshcore_client):
        """Returns contact when found by name."""
        from meshmon.meshcore_client import get_contact_by_name

        contact = MagicMock()
        contact.adv_name = "TestNode"
        mock_meshcore_client.get_contact_by_name.return_value = contact

        result = get_contact_by_name(mock_meshcore_client, "TestNode")

        assert result == contact
        mock_meshcore_client.get_contact_by_name.assert_called_once_with("TestNode")

    def test_returns_none_when_not_found(self, mock_meshcore_client):
        """Returns None when contact not found."""
        from meshmon.meshcore_client import get_contact_by_name

        mock_meshcore_client.get_contact_by_name.return_value = None

        result = get_contact_by_name(mock_meshcore_client, "NonExistent")

        assert result is None
        mock_meshcore_client.get_contact_by_name.assert_called_once_with("NonExistent")

    def test_returns_none_when_method_not_available(self):
        """Returns None when get_contact_by_name method not available."""
        from meshmon.meshcore_client import get_contact_by_name

        mc = MagicMock(spec=[])  # No methods

        result = get_contact_by_name(mc, "TestNode")

        assert result is None

    def test_returns_none_on_exception(self, mock_meshcore_client):
        """Returns None when method raises exception."""
        from meshmon.meshcore_client import get_contact_by_name

        mock_meshcore_client.get_contact_by_name.side_effect = RuntimeError("Connection lost")

        result = get_contact_by_name(mock_meshcore_client, "TestNode")

        assert result is None
        mock_meshcore_client.get_contact_by_name.assert_called_once_with("TestNode")


class TestGetContactByKeyPrefix:
    """Tests for get_contact_by_key_prefix function."""

    def test_returns_contact_when_found(self, mock_meshcore_client):
        """Returns contact when found by key prefix."""
        from meshmon.meshcore_client import get_contact_by_key_prefix

        contact = MagicMock()
        contact.pubkey_prefix = "abc123"
        mock_meshcore_client.get_contact_by_key_prefix.return_value = contact

        result = get_contact_by_key_prefix(mock_meshcore_client, "abc123")

        assert result == contact
        mock_meshcore_client.get_contact_by_key_prefix.assert_called_once_with("abc123")

    def test_returns_none_when_not_found(self, mock_meshcore_client):
        """Returns None when contact not found."""
        from meshmon.meshcore_client import get_contact_by_key_prefix

        mock_meshcore_client.get_contact_by_key_prefix.return_value = None

        result = get_contact_by_key_prefix(mock_meshcore_client, "xyz789")

        assert result is None
        mock_meshcore_client.get_contact_by_key_prefix.assert_called_once_with("xyz789")

    def test_returns_none_when_method_not_available(self):
        """Returns None when get_contact_by_key_prefix method not available."""
        from meshmon.meshcore_client import get_contact_by_key_prefix

        mc = MagicMock(spec=[])  # No methods

        result = get_contact_by_key_prefix(mc, "abc123")

        assert result is None

    def test_returns_none_on_exception(self, mock_meshcore_client):
        """Returns None when method raises exception."""
        from meshmon.meshcore_client import get_contact_by_key_prefix

        mock_meshcore_client.get_contact_by_key_prefix.side_effect = RuntimeError("Connection lost")

        result = get_contact_by_key_prefix(mock_meshcore_client, "abc123")

        assert result is None
        mock_meshcore_client.get_contact_by_key_prefix.assert_called_once_with("abc123")


class TestExtractContactInfo:
    """Tests for extract_contact_info function."""

    def test_extracts_from_dict_contact(self):
        """Extracts info from dict-based contact."""
        from meshmon.meshcore_client import extract_contact_info

        contact = {
            "adv_name": "TestNode",
            "name": "test",
            "pubkey_prefix": "abc123",
            "public_key": "abc123def456",
            "type": 1,
            "flags": 0,
        }

        result = extract_contact_info(contact)

        assert result["adv_name"] == "TestNode"
        assert result["name"] == "test"
        assert result["pubkey_prefix"] == "abc123"
        assert result["public_key"] == "abc123def456"
        assert result["type"] == 1
        assert result["flags"] == 0

    def test_extracts_from_object_contact(self):
        """Extracts info from object-based contact."""
        from meshmon.meshcore_client import extract_contact_info

        contact = SimpleNamespace(
            adv_name="TestNode",
            name="test",
            pubkey_prefix="abc123",
            public_key="abc123def456",
            type=1,
            flags=0,
        )

        result = extract_contact_info(contact)

        assert result["adv_name"] == "TestNode"
        assert result["name"] == "test"
        assert result["pubkey_prefix"] == "abc123"

    def test_converts_bytes_to_hex(self):
        """Converts bytes values to hex strings."""
        from meshmon.meshcore_client import extract_contact_info

        contact = {
            "adv_name": "TestNode",
            "public_key": bytes.fromhex("abc123def456"),
        }

        result = extract_contact_info(contact)

        assert result["adv_name"] == "TestNode"
        assert result["public_key"] == "abc123def456"

    def test_converts_bytes_from_object(self):
        """Converts bytes values from object attributes to hex."""
        from meshmon.meshcore_client import extract_contact_info

        contact = SimpleNamespace(
            adv_name="TestNode",
            public_key=bytes.fromhex("deadbeef"),
        )

        result = extract_contact_info(contact)

        assert result["adv_name"] == "TestNode"
        assert result["public_key"] == "deadbeef"

    def test_skips_none_values(self):
        """Skips None values in contact."""
        from meshmon.meshcore_client import extract_contact_info

        contact = {
            "adv_name": "TestNode",
            "name": None,
            "pubkey_prefix": None,
        }

        result = extract_contact_info(contact)

        assert result["adv_name"] == "TestNode"
        assert "name" not in result
        assert "pubkey_prefix" not in result

    def test_skips_missing_attributes(self):
        """Skips missing attributes in dict contact."""
        from meshmon.meshcore_client import extract_contact_info

        contact = {"adv_name": "TestNode"}

        result = extract_contact_info(contact)

        assert result == {"adv_name": "TestNode"}

    def test_empty_contact_returns_empty_dict(self):
        """Empty contact returns empty dict."""
        from meshmon.meshcore_client import extract_contact_info

        result = extract_contact_info({})

        assert result == {}


class TestListContactsSummary:
    """Tests for list_contacts_summary function."""

    def test_returns_list_of_contact_info(self):
        """Returns list of extracted contact info."""
        from meshmon.meshcore_client import list_contacts_summary

        contacts = [
            {"adv_name": "Node1", "type": 1},
            {"adv_name": "Node2", "type": 2},
            {"adv_name": "Node3", "type": 1},
        ]

        result = list_contacts_summary(contacts)

        assert len(result) == 3
        assert result[0]["adv_name"] == "Node1"
        assert result[1]["adv_name"] == "Node2"
        assert result[2]["adv_name"] == "Node3"

    def test_handles_mixed_contact_types(self):
        """Handles mix of dict and object contacts."""
        from meshmon.meshcore_client import list_contacts_summary

        obj_contact = SimpleNamespace(adv_name="ObjectNode")

        contacts = [
            {"adv_name": "DictNode"},
            obj_contact,
        ]

        result = list_contacts_summary(contacts)

        assert len(result) == 2
        assert result[0]["adv_name"] == "DictNode"
        assert result[1]["adv_name"] == "ObjectNode"

    def test_empty_list_returns_empty_list(self):
        """Empty contacts list returns empty list."""
        from meshmon.meshcore_client import list_contacts_summary

        result = list_contacts_summary([])

        assert result == []

    def test_preserves_order(self):
        """Preserves contact order in output."""
        from meshmon.meshcore_client import list_contacts_summary

        contacts = [
            {"adv_name": "Zebra"},
            {"adv_name": "Alpha"},
            {"adv_name": "Middle"},
        ]

        result = list_contacts_summary(contacts)

        assert result[0]["adv_name"] == "Zebra"
        assert result[1]["adv_name"] == "Alpha"
        assert result[2]["adv_name"] == "Middle"
