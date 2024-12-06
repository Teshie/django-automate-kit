from import_export import resources
from tablib import Dataset

from .error_codes import INVALID_HEADERS


class BaseResourceMixin(resources.ModelResource):
    class Meta:
        abstract = True
        exclude = ("id", "created_at", "updated_at", "created_by", "updated_by")

    def import_from_excel(self, file_binary):
        dataset = Dataset()

        dataset.load(file_binary)

        if dataset.headers is None:
            raise Exception(
                INVALID_HEADERS,
                "No Valid Headers Found. Please check the excel file and try again.",
            )

        if set(dataset.headers) != set(self.fields.keys()):
            raise Exception(
                INVALID_HEADERS,
                "Invalid Headers Found. Please check the excel file and try again.",
            )

        result = self.import_data(dataset, dry_run=False)
        return result

    def export_to_file(self, extension="xlsx"):
        dataset = self.export()
        return dataset.export(format=extension)
