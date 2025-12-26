# Generated migration for FamilyMember model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0009_add_devotion_enabled'),
    ]

    operations = [
        migrations.CreateModel(
            name='FamilyMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('admin', 'Admin'), ('member', 'Member')], default='member', help_text='Admin is the account owner, members are family', max_length=20)),
                ('status', models.CharField(choices=[('active', 'Active'), ('removed', 'Removed'), ('pending', 'Pending Invitation')], default='active', help_text='Current status of family membership', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('removed_at', models.DateTimeField(blank=True, help_text='When member was removed from family', null=True)),
                ('admin', models.ForeignKey(help_text='The family plan admin/owner', on_delete=django.db.models.deletion.CASCADE, related_name='family_members', to=settings.AUTH_USER_MODEL)),
                ('member', models.ForeignKey(help_text='The family member with access', on_delete=django.db.models.deletion.CASCADE, related_name='family_memberships', to=settings.AUTH_USER_MODEL)),
                ('removed_by', models.ForeignKey(blank=True, help_text='Who removed this member', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='removed_family_members', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [models.Index(fields=['admin', 'status'], name='accounts_fa_admin_i_7e4c6a_idx'), models.Index(fields=['member', 'status'], name='accounts_fa_member__3fa1de_idx')],
                'unique_together': {('admin', 'member')},
            },
        ),
    ]
