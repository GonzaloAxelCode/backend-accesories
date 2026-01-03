from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tienda", "0014_remove_tienda_owner"),
    ]

    operations = [

        migrations.AddField(
            model_name="tienda",
            name="razon_social",
            field=models.CharField(max_length=150, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="tienda",
            name="email",
            field=models.EmailField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="tienda",
            name="sol_user",
            field=models.CharField(max_length=50, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="tienda",
            name="sol_password",
            field=models.TextField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="tienda",
            name="logo_img",
            field=models.ImageField(upload_to="tienda_logos/", null=True, blank=True),
        ),
    ]
