import base64
from enum import Enum

import graphene
import datetime
from .resources import BaseResourceMixin
from .models import AutomateKitModel
from .mutation import MutationMixin
from .types import ImportInputType, ExportInputType, ImportOutputType, ExportOutputType


class ImportExportMutationGenerator(MutationMixin):
    @classmethod
    def resolve_related_object(
        cls, model: AutomateKitModel, field_name, value, info=None
    ):
        related_model = model._meta.get_field(field_name).related_model
        if related_model == cls.user_model() and value == "default_id":
            if info and info.context.user:
                value = info.context.user
            else:
                return None
                value = None

        try:
            return related_model.objects.get(pk=value)
        except related_model.DoesNotExist:
            raise Exception(f"{related_model.__name__} with pk {value} does not exist.")

    @classmethod
    def resolve_many_to_many_objects(
        cls, model: AutomateKitModel, field_name, value: list
    ):
        related_model = model._meta.get_field(field_name).related_model
        related_objects = []
        if not isinstance(value, list):
            raise Exception(f"{field_name}_pks must be list of related object")

        for pk in value:
            try:
                related_objects.append(related_model.objects.get(pk=pk))
            except related_model.DoesNotExist:
                raise Exception(
                    f"{related_model.__name__} with pk {value} does not exist."
                )

        return related_objects

    @classmethod
    def generate_import_mutate_method_for_model(cls, model: AutomateKitModel):
        def _(root, info, *args, **kwargs):
            cls.check_permission(info.context.user, model)
            inputs = kwargs.get("inputs")

            resource_class = type(
                f"{model.__name__}Resource",
                (BaseResourceMixin,),
                {
                    "Meta": type(
                        "Meta",
                        (),
                        {
                            "model": model,
                            "import_id_fields": model.import_id_fields
                        }
                    )
                }
            )

            if isinstance(inputs, dict):
                inputs = [inputs]
            created_data = []
            for _input in inputs:
                file_content = base64.b64decode(_input['file_content'])
                _resource = resource_class()
                result = _resource.import_from_excel(file_content)
                data = {
                    "inserted": result.totals["new"],
                    "updated": result.totals["update"],
                    "deleted": result.totals["delete"],
                    "failed": result.totals["error"],
                    "total": result.total_rows,
                }
                created_data.append(data)

            return {"data": created_data}

        return _

    @classmethod
    def generate_export_mutate_method_for_model(cls, model: AutomateKitModel):
        def _(root, info, *args, **kwargs):
            cls.check_permission(info.context.user, model)
            inputs = kwargs.get("inputs")

            resource_class = type(
                f"{model.__name__}Resource",
                (BaseResourceMixin,),
                {
                    "Meta": type(
                        "Meta",
                        (),
                        {
                            "model": model,
                            "import_id_fields": model.import_id_fields
                        }
                    )
                }
            )

            if isinstance(inputs, dict):
                inputs = [inputs]
            created_data = []
            for _input in inputs:
                extension = _input['extension'].value
                _resource = resource_class()
                _data = _resource.export_to_file(extension=extension)
                filename = f"Export-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.{_resource._meta.model.__name__}.{extension}"
                data = {
                    "file_content": _data,
                    "filename": filename,
                    "extension": extension
                }
                created_data.append(data)

            return {"data": created_data}

        return _

    @classmethod
    def generate_query_for_model(cls, model: AutomateKitModel):
        if not getattr(model, "import_id_fields"):
            return

        import_argument_class = type(
            "Arguments",
            (),
            {
                "inputs": ImportInputType(required=True)
            }
        )
        export_argument_class = type(
            "Arguments",
            (),
            {
                "inputs": ExportInputType(required=True)
            }
        )

        import_mutation_type = type(
            f"{cls.to_snake_case(model.__name__)}ImportMutation",
            (graphene.Mutation,),
            {
                "Arguments": import_argument_class,
                "data": graphene.List(ImportOutputType),
                "mutate": cls.generate_import_mutate_method_for_model(model),
            },
        )
        export_mutation_type = type(
            f"{cls.to_snake_case(model.__name__)}ExportMutation",
            (graphene.Mutation,),
            {
                "Arguments": export_argument_class,
                "data": graphene.List(ExportOutputType),
                "mutate": cls.generate_export_mutate_method_for_model(model),
            },
        )

        setattr(
            cls, f"import_{cls.to_snake_case(model.__name__)}", import_mutation_type.Field()
        )
        setattr(
            cls, f"export_{cls.to_snake_case(model.__name__)}", export_mutation_type.Field()
        )
