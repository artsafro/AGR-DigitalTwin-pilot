"""Copy-only #298 output guards. new-case: job-local immutable input boundary."""
from pathlib import Path


def new_output(source, output):
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if source.is_dir() and output.is_relative_to(source):
        raise ValueError(f'output is within protected source {source}')
    if output == source or output.exists():
        raise ValueError(f'refusing existing/aliased output {output}')
    return output
