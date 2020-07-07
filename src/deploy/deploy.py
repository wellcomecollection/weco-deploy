import click


@click.group()
def cli():
    pass


@click.command()
@click.option("--foo", default="bar", help="Placeholder")
def run(foo):
    print(foo)


def main():
    cli.add_command(run)
    cli()
