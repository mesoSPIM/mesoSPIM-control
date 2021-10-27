Github contains multiple tools that allow you to switch seamlessly between code versions, track changes, and collaborate efficiently.
Initially it can be confusing, but it's OK!

## Branches
The `master` branch contains stable, always deployable code, but it is often outdated. 
We follow the [Github worflow](https://guides.github.com/introduction/flow/) with the `development` branch as the main.
It is recommended to use the `development` branch as a starting point, which contains the latest bugfixes and features. 
However, some features are experimental and not yet thoroughly tested. 

Your workflow may look as follows:
0. Fork the repository.
1. Check out the `development` branch and see if it works on your mesoSPIM setup.
2. Create a local branch from `development` (e.g. `dev-my-feature`), and start experimenting with the code.
3. Once you are satisfied with your new feature, create a pull request back to the `development` branch, 
   we will review and merge it.
   Small bugfixes can be pull-requested directly from your forked `development` branch, without creating a new branch. This simplifies the workflow.
4. After your commits were merged into `development`, the code is stable, and you are done with `my-feature` branch, don't forget to delete it. This will keep things tidy.

Stable releases from `development` will be merged into `master` once every few months.

## Reporting bugs and issues
If you find a bug or unexpected behavior, please report an [issue](https://github.com/mesoSPIM/mesoSPIM-control/issues)! We will try to fix it or find another solution.

## Testing, testing
Because mesoSPIM is a complex hardware-software system in active use and often individually customized, it is quite difficult to run good tests that cover your and other systems. So, be careful! 
Test the code on your system, ideally in acquisition experiment that saves the "data" (with or without a sample), and then let us test it on our systems.

It is a good habit to write simple [unit tests](https://github.com/mesoSPIM/mesoSPIM-control/tree/development/mesoSPIM/test)
**before** you implement a feature (so-called test-driven development, TDD), this helps immensely in debugging.

## Share you ideas and feature requests
If you have an idea or feature request that can significantly improve mesosPIM user experience - 
share it in [Discussions](https://github.com/mesoSPIM/mesoSPIM-control/discussions). We can implement it!

## Enjoy!
Any contribution is welcome, and tinkering with mesoSPIM is fun. So, enjoy it wth us!
