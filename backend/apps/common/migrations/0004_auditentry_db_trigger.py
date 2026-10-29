from django.db import migrations


def create_audit_triggers(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == 'postgresql':
        schema_editor.execute("""
            CREATE OR REPLACE FUNCTION prevent_audit_tampering()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'AuditEntry is append-only. Modification or deletion is strictly forbidden by database trigger.';
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS trg_auditentry_prevent_tamper ON common_auditentry;
            CREATE TRIGGER trg_auditentry_prevent_tamper
            BEFORE UPDATE OR DELETE ON common_auditentry
            FOR EACH ROW EXECUTE FUNCTION prevent_audit_tampering();
        """)
    elif vendor == 'sqlite':
        schema_editor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_auditentry_no_update
            BEFORE UPDATE ON common_auditentry
            BEGIN
                SELECT RAISE(ABORT, 'AuditEntry is append-only. Modification is strictly forbidden by database trigger.');
            END;
        """)
        schema_editor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_auditentry_no_delete
            BEFORE DELETE ON common_auditentry
            BEGIN
                SELECT RAISE(ABORT, 'AuditEntry is append-only. Deletion is strictly forbidden by database trigger.');
            END;
        """)


def drop_audit_triggers(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == 'postgresql':
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS trg_auditentry_prevent_tamper ON common_auditentry;
            DROP FUNCTION IF EXISTS prevent_audit_tampering();
        """)
    elif vendor == 'sqlite':
        schema_editor.execute("DROP TRIGGER IF EXISTS trg_auditentry_no_update;")
        schema_editor.execute("DROP TRIGGER IF EXISTS trg_auditentry_no_delete;")


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0003_auditentry'),
    ]

    operations = [
        migrations.RunPython(create_audit_triggers, drop_audit_triggers),
    ]
