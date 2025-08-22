package cleanup scripts
====

* Remove old cache.pickle
* Update `const.py`
* Update and run `gen-cleanup-list` to get data
  * Bind build's PostgreSQL socket
* Create issue
* Update and run `gen-cleanup-list` to post comments
* Repeat as will
  * Run `gen-removed-maintainership` to generate the json file
  * Check if anyone hasn't take action yet
  * Run `gen-update` to generate the YAML file
  * Check the packages to be removed
* Update and run `mass-orphan` to
  * update the git repository
  * check issues about to open
  * actually open issues
