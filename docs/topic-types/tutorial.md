# Tutorial topic

--8<-- "docs/topic-types/single-source.md"

The purpose of a tutorial topic is to walk through a procedure or workflow with the goal of learning. It is a lesson primarily for illustrating generalizable principles rather than completing the specific task. Avoid digression that includes reference content or explanation content--link to those topics instead. This helps keep tutorials focused and makes maintenance of content easier. 

We recommend creating a top-level "Tutorials" section that includes all tutorial topics (see [Tutorials](../tutorials/index.md)). For additional information on how to structure tutorials, see [Diataxis](https://diataxis.fr/tutorials/).

## Titles

Use imperative verbs for tutorial topics. For example, "Get Started," "Calibrate the Model," or "Configure a Vaccination Campaign." Avoid gerunds (-ing verbs) because they can be ambiguous, sometimes functioning as a verb, adjective, or noun. This can create confusion, especially in translation.

## Jupyter notebooks

When possible, we recommend using Jupyter notebooks for tutorial content. Notebooks can run both Python and R code. Notebooks are executed as part of the MkDocs documentation build, so if the content becomes outdated, you will see an error. Tutorials can be some of the most challenging topic types to keep from becoming stale, so this integrated testing is very valuable. See the tutorial [Get Started](../tutorials/intro.ipynb) for an example. Jupyter notebook files (.ipynb) should be listed in the mkdocs.yml nav section the same way typical Markdown (.md) files are. 

All packages needed to run the Jupyter notebook must be installed via requirements.txt.

### R packages

For R packages, you can use `knitr` to convert Rmarkdown files to Markdown so they can be integrated into a MkDocs project. Code samples by default use Python syntax highlighting, but you can specify R highlighting as below:

```r
# Your R code goes here
print("Hello from R!")
x <- 1:5
mean(x)
```

Additionally, you can use `pymdownx.snippets` to integrate code samples from separate R code to make maintenance simpler. 