import click
import inflection


@click.command()
@click.argument('version')
@click.argument('name')
@click.option('--model')
@click.option('--plural-name')
def get_context(version, name, model, plural_name):
    name = inflection.underscore(inflection.singularize(name))
    model = model or name
    model_class_name = inflection.camelize(model)
    class_name = inflection.camelize(name)
    serializer_class_name = class_name + 'Serializer'
    viewset_class_name = class_name + 'ViewSet'
    plural_name = plural_name or inflection.pluralize(name)
    return {
        'version': version,
        'serializer_class_name': serializer_class_name,
        'viewset_class_name': viewset_class_name,
        'model_class_name': model_class_name,
        'name': name,
        'plural_name': plural_name
    }
