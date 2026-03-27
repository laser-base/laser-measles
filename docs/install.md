# Installation/get started

Depending on the structure of the rest of the content, you may want to include either an "Installation" topic or a "Get started" topic. Generally, if there is a single "Get started" tutorial or if installation is a complex process, use a separate "Installation" topic. These topics should follow the guidelines for a [How-to topic](topic-types/howto.md). 

If installation is a simple process, such as a `pip` install, and there is a recommended path for getting started with a project or package  we recommend including a "Get Started" topic with information about that onboarding path. This may include a brief overview of the project, installation instructions, tutorials, etc.

MkDocs content tabs can be a neat way to present different instructions for different operating systems or Python installations. For example:

=== "Python"

    ```
    python -m venv <env-name>
    ```
=== "Anaconda"

    ```
    conda create -n <env-name>
    ```

## Tutorials

For a "Get started" topic, it's good practice to link to one or more of the beginning tutorials. For example, the tutorial [Get started](tutorials/intro.ipynb) introduces the fundamentals of the package by walking through a typical workflow. 