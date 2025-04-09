from django.core.management.base import BaseCommand
import sys
import os
import re


class Command(BaseCommand):
    help = f"Generates a URL based on the view name"

    def add_arguments(self, parser):
        parser.add_argument("app", nargs="+", type=str)

    def get_model_details(self, file):

        temp_list = []
        fields = []
        models = []
        model_counter = -1

        with open(file, "r") as fp:

            lines = fp.readlines()

            for line in lines:
                line = line.strip()

                if line.endswith("(models.Model):"):
                    model_name = line.split()[1].split("(")[0]
                    models.append(model_name)
                    if model_counter >= 0:
                        temp = {"model": models[model_counter], "fields": fields}
                        temp_list.append(temp)
                    model_counter += 1
                    fields = []

                if "= models." in line:
                    field_name = line.split("=")[0].strip()
                    fields.append(field_name)

        temp = {"model": models[model_counter], "fields": fields}
        temp_list.append(temp)

        return temp_list

    def register_admin_site(self, model):
        model_name = model.get("model")
        string = f"admin.site.register({model_name})"

        print(string)

    def handle(self, *args, **kwargs):

        app = kwargs.get("app", [])[0]
        # Switch to app directory
        os.chdir(f"{app}")
        print(os.getcwd())

        if "models.py" in os.listdir():
            model_details = self.get_model_details("models.py")
            # print(model_details)

        string = "from django.contrib import admin\n"
        string += f"from {app}.models import ("
        for model in model_details:
            model_name = model.get("model")
            string += f"{model_name}, "
        string += ")"
        print(string)
        print()
        for model in model_details:
            self.register_admin_site(model)
