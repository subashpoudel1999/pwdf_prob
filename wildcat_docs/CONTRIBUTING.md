Contributing
============

Contributions are welcome from the community. Questions can be asked on the
[issues page][1]. Before creating a new issue, please take a moment to search
and make sure a similar issue does not already exist. If one does exist, you
can comment (most simply even with just a `:+1:`) to show your support for that
issue.

If you have direct contributions you would like considered for incorporation
into the project you can [fork this repository][2] and
[submit a merge request][3] for review.

[1]: https://code.usgs.gov/ghsc/lhp/wildcat/issues
[2]: https://docs.gitlab.com/ee/user/project/repository/forking_workflow.html#creating-a-fork
[3]: https://docs.gitlab.com/ee/user/project/merge_requests/creating_merge_requests.html


## Installation
We recommend using the included poetry scripts to help ensure your contributions meet the project's standards. These scripts require a development installation of pfdf. You can implement this install using:
```
poetry install --with dev
```
All commands described on this page assume a development installation.

## Formatting
This project uses `isort` and `black` to format the code. You can apply these formatters using:
```
poe format
```
This should format the code within the `wildcat` and `tests` directories. We also note that many IDEs include tools to automatically apply these formats. 

Note that you can also use:
```
poe lint
```
to verify that all code is formatted correctly. The Gitlab pipeline requires that this check passes before code can be merged.

## Testing
This project uses the `pytest` framework to implement tests, and the Gitlab pipeline requires that all tests pass before new code can be added. As a rule, all new code should include accompanying tests. The tests should follow a parallel structure to the `wildcat` package, and the tests for a given module should be name `test_<module>.py`. One exception is for modules that test the CLI subparsers. These should follow the naming scheme `test_<module>_parser.py` to avoid namespace conflicts.

Within a test module, multiple tests for the same function should be grouped into a class. For large classes, the tests for each property or method should likewise be grouped into a class. For small classes, it may be appropriate to group all tests into a single class. Test class names should use capitalized camel-case. Underscores are discouraged, except when needed to distinguish between public and private routines with the same name. Individual tests should be named using standard Python snakecase (lowercase separated by underscores).

Note that you can check the status of the tests using:
```
poe tests
```