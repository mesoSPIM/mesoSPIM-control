Github contains multiple tools that allow you to switch seamlessly between code versions, track changes, and collaborate efficiently.
Initially it can be confusing, but it's OK! Invest some time in learning how github works (especially branches and commits), this will pay off!

## Branches
The `master` branch contains stable, always deployable code, but it is often outdated. 
It is recommended to use the `development` branch, which contains the latest bugfixes and features. 
However, some features are experimental and not yet thoroughly tested. 
If the `development` branch works for you smoothly, make a copy of it: create a local branch, name it e.g. `dev-INSTITUTE-NAME`. 
This will allow you to switch back to safety (`dev-INSTITUTE-NAME`) and run you experiments smoothly, if some future commits in `development` turn out to be buggy. 
You can always update your local branch from `development` later.

Stable releases from `development` will be merged into `master` once every few months.

## Reporting bugs and issues
If you find a bug or unexpected behavior, please report an [issue](https://github.com/mesoSPIM/mesoSPIM-control/issues)! We will try to fix it or find another solution.

## Changing code
We follow the [Github worflow](https://guides.github.com/introduction/flow/) with the `development` branch as the main. 
So, fork the repository, create your branch `my-feature` from `development`, and you are free to play. 
Once the feature or bugfix work on your system, and you are ready to share, open a pull request. 

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
