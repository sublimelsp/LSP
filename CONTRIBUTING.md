# Contributor guidelines

## Before you start

LSP is a universal language server package.
It is not the place for language-specific logic, features or workarounds.

Sublime Text is not an IDE.
Sublime Text users may appreciate IDE-like features, but a significant number of users will want to turn these features off due to performance or to keep the package "out of the way".

Please feel free to create an issue before coding:

* If you are unsure your proposal is suitable
* If you are unsure your solution will be technically sound

The issues also allow you to gather some feedback and help from other contributors.

## Coding

Sublime Text 3 bundles a Python 3.3, please be sure to set up your environment to match.
LSP uses two flake8 and mypy to provide some code quality assurances.
I highly recommend enabling plugins for these in your Python coding environment.
If you have these tools available on your machine, you can check your work with:

```
flake8 main.py
mypy main.py
```

## Testing

Please consider testing your work with other language servers, even if you do not use them.
The Javascript/Typescript language server is a good example, it has a fairly complete feature set.

## Submitting

Before you submit your pull request, please review the following:

* Any unrelated changes in there?
* Is it a bug fix? Please link the issue or attach repro, logs, screenshots etc.
* Is it a feature? Please attach screenshots / GIFs for visual changes.

I will try to help you get the PR in mergeable shape within a reasonable time, but it may take a few days.
It is best if you check your Github notifications in the meantime!