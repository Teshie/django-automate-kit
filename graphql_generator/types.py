import re

import graphene
from django.apps import apps
from django.contrib.auth import get_user_model
from graphene_django import DjangoObjectType
import base64
from .filters import (
    DateFilterKeywordsInputType,
    NumberFilterKeywordsInputType,
    StringFilterKeywordsInputType,
)
from .models import AutomateKitModel


class ImportExportExtensions(graphene.Enum):
    xlsx = "xlsx"
    csv = "csv"
    xls = "xls"


class ImportInputType(graphene.InputObjectType):
    file_content = graphene.String(required=True)


class ExportInputType(graphene.InputObjectType):
    extension = ImportExportExtensions(required=True)


class ExportOutputType(graphene.ObjectType):
    file_content = graphene.Base64()
    filename = graphene.String()
    extension = graphene.String()


class ImportOutputType(graphene.ObjectType):
    inserted = graphene.Int()
    updated = graphene.Int()
    deleted = graphene.Int()
    failed = graphene.Int()
    total = graphene.Int()


class TypeGenerator:
    user_model = lambda: get_user_model()
    generated_types = dict()
    non_filterable_field_types = [
        "ManyToManyRel",
        "ManyToOneRel",
        "OneToOneRel",
        "ImageField",
        "FileField",
        "JSONField",
    ]

    @classmethod
    def to_snake_case(cls, name):
        name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        name = re.sub("__([A-Z])", r"_\1", name)
        name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name)
        return name.lower()

    @classmethod
    def include_apps(cls, apps: list):
        models = cls.find_all_models(_apps=apps)
        for model in models:
            cls.generate_query_for_model(model=model)

    @classmethod
    def include_models(cls, models: list):
        for model in models:
            cls.generate_query_for_model(model=model)

    @classmethod
    def generate_query_for_model(cls, model: AutomateKitModel):
        raise NotImplementedError()

    @classmethod
    def query_set_builder(cls, where: dict):
        _ = {}
        if not where:
            return _

        for field, lookup in where.items():
            for lookup_word, value in lookup.items():
                if isinstance(value, dict):
                    _lookup_word, _value = value.popitem()
                    _[f"{field}__{lookup_word}__{_lookup_word}"] = _value
                else:
                    _[f"{field}__{lookup_word}"] = value
        return _

    @classmethod
    def where_clause_from_internal_field(cls, internal_type, field):
        date_fields = ["DateTimeField", "DateField"]
        number_fields = [
            "IntegerField",
            "FloatField",
            "DecimalField",
            "BigAutoField",
            "AutoField",
        ]
        foreign_key_fields = ["ForeignKey"]

        if internal_type in cls.non_filterable_field_types:
            return None

        if internal_type in date_fields:
            return DateFilterKeywordsInputType()

        if internal_type in number_fields:
            return NumberFilterKeywordsInputType()

        if internal_type in foreign_key_fields:
            pk_internal_type = field.related_model._meta.pk.get_internal_type()
            return cls.where_clause_from_internal_field(pk_internal_type, field)

        return StringFilterKeywordsInputType()

    @classmethod
    def generate_where_clause(cls, model, extra_name=None):
        attrs = {}
        for field in model._meta.fields:
            internal_type = field.get_internal_type()
            field_where_clause = cls.where_clause_from_internal_field(
                internal_type, field
            )
            if not field_where_clause:
                continue

            if internal_type == "ForeignKey":
                pass
                # attrs[f'{field.name}__id'] = field_where_clause
            else:
                attrs[field.name] = field_where_clause
        name = f"{model.__name__}FilterCLass"
        if extra_name:
            name += f"_{extra_name}"
            return type(name, (graphene.InputObjectType,), {**attrs})
        return type(name, (graphene.InputObjectType,), {**attrs})()

    @classmethod
    def generate_where_clause_deep(cls, model):
        attrs = {}
        for field in model._meta.fields:
            internal_type = field.get_internal_type()
            field_where_clause = cls.where_clause_from_internal_field(
                internal_type, field
            )
            if not field_where_clause:
                continue

            if internal_type == "ForeignKey":
                attrs[f"{field.name}"] = cls.generate_where_clause(
                    field.related_model, extra_name=model.__name__
                )()
            else:
                attrs[field.name] = field_where_clause

        return type(
            f"{model.__name__}DeepFilterCLass", (graphene.InputObjectType,), {**attrs}
        )

    @classmethod
    def generate_orderby_clause(cls, model):
        attrs = {}
        for field in model._meta.fields:
            attrs[f"{field.name}_ASC"] = f"{field.name}"
            attrs[f"{field.name}_DESC"] = f"-{field.name}"

        return type(f"{model.__name__}OrderCLass", (graphene.Enum,), {**attrs})()

    @classmethod
    def get_or_generate_django_object_type(cls, model: AutomateKitModel):
        if model in cls.generated_types:
            return cls.generated_types[model]

        return cls.generate_model_type(model)

    @classmethod
    def generate_model_type(cls, model: AutomateKitModel):
        model_type = type(
            f"{model.__name__.lower()}",
            (DjangoObjectType,),
            {
                "Meta": type(
                    "Meta",
                    (),
                    {"model": model, "fields": "__all__"},
                ),
                **cls.get_method_fields(model)
            },
        )
        cls.generated_types[model] = model_type
        return model_type

    @classmethod
    def get_method_fields(cls, model):
        fields = {}
        if hasattr(model, "include_methods_fields"):
            if not isinstance(model.include_methods_fields, dict):
                raise Exception(
                    f"include_methods_fields must be DICT on model {model}"
                )
            fields = model.include_methods_fields
        return fields

    @classmethod
    def find_all_models(cls, _apps: list):
        all_apps = [apps.get_app_config(app) for app in _apps]
        for app in all_apps:
            models = app.get_models()
            for model in models:
                if not issubclass(model, AutomateKitModel):
                    continue
                if model.exclude_model:
                    continue
                yield model

    @classmethod
    def check_permission(cls, user, model):
        if not hasattr(model, "graphql_permissions"):
            return True

        if not model.graphql_permissions:
            return True

        if not user.is_authenticated:
            raise Exception("Permission Denied")

        if model.graphql_permissions == ("is_authenticated",):
            return True

        if not user.has_perms(model.graphql_permissions):
            raise Exception("Permission Denied")

        return True
