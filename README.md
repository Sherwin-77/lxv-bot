Discord Bot for LXV server

![Discord](https://img.shields.io/discord/714152739252338749?style=for-the-badge)

## Running

No you don't, this bot is running for specific demand & requirement for server

However if you insist, then I think this meme might is perfect for you:

![image](https://github.com/user-attachments/assets/36106d2a-a3e3-40c4-b994-94d9155afd19)

1. Python Runtime
   This bot run with **Python 3.12** and [discord.py](https://github.com/Rapptz/discord.py) requires **Python 3.8 or higher**, do your own research for running other than specified version
2. Setting Environment
   It is recommended to use virtual environment, the simple way to do this is create [venv](https://docs.python.org/3/library/venv.html) from python
   ```.sh
   python -m venv venv
   ```
   If success, you need to activate virtual environment before installing / running. Activation depends on platform (e.g `source venv/bin/activate` for linux and `venv/Scripts/Activate.ps1` for windows)
3. Set variables
   Copy `.env.example` to `.env` and fill the field given, change content inside `consts.py` to fit your server
4. Installing
   After setting up environment, you need to install library required for bot. To do this, run:
   ```.sh
   pip install -r requriements.txt
   ```
5. Migration
   This bot uses [alembic](https://pypi.org/project/alembic/) for creating & running migration, just run `alembic migrate head` to migrate your database
6. Running
   Congratulations, you managed to set up my bot, the last step is run `python main.py`. You might want to set scheduler to set auto restart & stuff
