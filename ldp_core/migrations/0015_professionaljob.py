from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ldp_core', '0014_persontransferhistory'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProfessionalJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job_title', models.CharField(max_length=255, verbose_name='Job Title / Position')),
                ('employer', models.CharField(max_length=255, verbose_name='Employer / Company')),
                ('employment_type', models.CharField(
                    choices=[
                        ('FULL_TIME', 'Full-time'),
                        ('PART_TIME', 'Part-time'),
                        ('CONTRACT', 'Contract'),
                        ('FREELANCE', 'Freelance / Self-employed'),
                        ('INTERNSHIP', 'Internship / OJT'),
                        ('VOLUNTEER', 'Volunteer'),
                        ('OTHER', 'Other'),
                    ],
                    default='FULL_TIME', max_length=20, verbose_name='Employment Type'
                )),
                ('location', models.CharField(blank=True, max_length=255, verbose_name='Location / Office')),
                ('start_date', models.DateField(verbose_name='Start Date')),
                ('end_date', models.DateField(blank=True, null=True, verbose_name='End Date')),
                ('is_current', models.BooleanField(default=False, verbose_name='Currently Working Here')),
                ('description', models.TextField(blank=True, verbose_name='Responsibilities / Notes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('person', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='jobs', to='ldp_core.person'
                )),
            ],
            options={
                'verbose_name': 'Professional Job',
                'verbose_name_plural': 'Professional Jobs',
                'ordering': ['-is_current', '-start_date'],
            },
        ),
    ]
