# The DB Folder
This is where all the auto-generated database files will be stored. This bot will use a similar system as MarwynnBot, except now that I actually know what I'm doing, the `.json` files will be stored in an easy to access directory and can be backed up and exported efficiently. For security and privacy reasons, the database files are ignored in this repository.

The files that will be created are as follows:
```
./db
  ↳
    - actionstats.json*
    - mutes.json*
    - playlists.json*
    - reactionroles.json
    - tags.json*
    - warns.json*
```
\**These files will be created when a specific command is executed for the first time. What I have implemented is a check to see if a file exists, if not, return an error message.*