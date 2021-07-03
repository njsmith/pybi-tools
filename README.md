To add new pybis:

- on sidra, add to built/ directory
- on sidra, run `python3 regen-simple.py`
- go to the $web container in azure portal and get a SAS token
- on sidra, *in built/ directory*, run:

  ```
  az storage blob sync -s . --account-name pybi --container '$web' --sas-token [token]
  ```
