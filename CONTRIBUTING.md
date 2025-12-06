Github contains multiple tools that allow you to switch seamlessly between code versions, track changes, and collaborate efficiently.
Initially it can be confusing, but it's OK!

## Branches
The `master` branch contains stable, always deployable code, well tested on actual hardware. 
We follow the [Github worflow](https://guides.github.com/introduction/flow/) with the `release/candidate-py12` being the branch where we test new features. We recommend using Github Desktop application for easy branch management.

## Contributing new features
We welcome contributions of new features, bugfixes, and improvements from the community!
It is recommended to use the `release/candidate-py12` branch as a starting point for development.

Your workflow may look as follows:

0. Fork the repository.
1. Check out the `release/candidate-py12` branch and see if it works in demo mode and on your actual mesoSPIM setup.
2. Create a local branch from `release/candidate-py12` (e.g. `dev-my-feature`), and start experimenting with the code.
3. Once you are satisfied with your new feature, create a pull request back to the `release/candidate-py12` branch, we will review and merge it.
4. After your commits were merged into `release/candidate-py12`, the code is stable, and you are done with `my-feature` branch, you can delete it. This will keep things tidy.

Stable releases from `release/candidate-py12` will be merged into `master` once every few months after testing on several physical setups with multiple users. Often users are the ones who report bugs and issues, because they use the software in diverse real-world scenarios.

## Reporting bugs and issues
If you find a bug or unexpected behavior, please report an [issue](https://github.com/mesoSPIM/mesoSPIM-control/issues)! We will try to fix it or find another solution.

## Testing, testing
Because mesoSPIM is a complex hardware-software-user system and often individually customized, it is quite difficult to run good tests that cover such diverse systems. So, be careful! 
Test the code fist in hardware-simulation mode (using `demo_config.py` file), then on real hardware, ideally with some sample.

It is a good habit to write simple [unit tests](https://github.com/mesoSPIM/mesoSPIM-control/tree/release/candidate-py12/mesoSPIM/test)
**before** you implement a feature (so-called test-driven release/candidate-py12, TDD), this helps immensely in debugging. But we understand that this is not always possible, and can be very time-consuming.

## Share you ideas and feature requests
If you have an idea or feature request that can significantly improve mesosPIM user experience - 
share it in [Forum](https://forum.image.sc/tag/mesospim). We can implement it!

## Enjoy!
Any contribution is welcome, and tinkering with mesoSPIM is fun. So, enjoy it!
