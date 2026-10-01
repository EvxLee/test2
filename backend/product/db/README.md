# README

Steps:

- [README](#readme)
  - [Cleaning out the database (so that you may re-deploy from scratch)](#cleaning-out-the-database-so-that-you-may-re-deploy-from-scratch)
  - [Deploying the Database](#deploying-the-database)
  - [Populating the database](#populating-the-database)

## Cleaning out the database (so that you may re-deploy from scratch)

**THIS WILL DESTROY ALL DATA!!!!!** (and that may be totally fine, because this is a demo product anyway)

Typically, if you're just adding stuff, you can just re-run `./deploy.sh` as described above, but in case you cannot (you're not just adding things, you're actually modifying pre-existing schema objects) or want to clear out everything for absolutely sure:

Connect to the database using `psql` and execute these commands (not needed anymore, this is now done by the `deploy.sh` script, but in case you want to know or make double certain):

```sql
drop schema "Patients" cascade;
drop schema "Nurses" cascade;
```

Each of these commands drops the named schema, and everything in it.

## Deploying the Database

```sh
# One liner
PG_URI="postgresql://<user>:<password>@<hostname>:<port>/<database>" ./deploy.sh

# 2 lines
export PG_URI="postgresql://<user>:<password>@<hostname>:<port>/<database>"
./deploy.sh
```

You can get the value for `PG_URI` from your managed database provider's connection details page; connect as the admin user to database `atlas`.

> If you are deploying the database for the _very first time_ against a totally clean new managed DB cluster
> then uncomment the designated lines in the `000-initialize.sql` script (see the script for more info on which lines)

