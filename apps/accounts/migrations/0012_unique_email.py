from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_add_temperature_unit'),
    ]

    operations = [
        migrations.RunSQL(
            # Add unique constraint on email
            sql="ALTER TABLE auth_user ADD CONSTRAINT auth_user_email_unique UNIQUE (email);",
            reverse_sql="ALTER TABLE auth_user DROP CONSTRAINT auth_user_email_unique;",
        ),
    ]
