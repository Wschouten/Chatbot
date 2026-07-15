"""Regression tests for the Fase 3B audit fixes (AUDIT-2026-07-11).

B7: the single-conversation metadata (admin_db.get_metadata) must include
`messageMetadata`, otherwise the portal's per-conversation refresh wipes
message-level labels/ratings after every mutation.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_get_metadata_includes_message_metadata(tmp_path):
    os.environ["PORTAL_DB_PATH"] = str(tmp_path / "portal_test.db")
    try:
        import admin_db
        import app as flask_app

        admin_db.init_db()
        with flask_app.app.app_context():
            # A conversation_metadata row must exist for get_metadata to return.
            admin_db.upsert_metadata("sess_b7", status="open")
            admin_db.add_message_label("sess_b7", "msg_0", "needs-review")
            admin_db.set_message_rating("sess_b7", "msg_1", 5)

            meta = admin_db.get_metadata("sess_b7")

        assert meta is not None
        assert "messageMetadata" in meta, "get_metadata must expose messageMetadata (B7)"
        assert meta["messageMetadata"]["msg_0"]["labels"] == ["needs-review"]
        assert meta["messageMetadata"]["msg_1"]["rating"] == 5
    finally:
        os.environ.pop("PORTAL_DB_PATH", None)
