Discord Bot for LXV server

![Discord](https://img.shields.io/discord/714152739252338749?style=for-the-badge)

## Running

No you don't, this bot is running for specific demand & requirement for server

However if you insist, this meme might be perfect for you

![image](https://github.com/user-attachments/assets/36106d2a-a3e3-40c4-b994-94d9155afd19)

1. Set up environment
   This bot run with **Python 3.12**. Do your own research if running lower version. It is recommended to use virtual environment, the simple way to do this is create [venv](https://docs.python.org/3/library/venv.html) from python
   ```.sh
   python -m venv venv
   ```
   If success, you need to activate virtual environment before installing / running. Activation depends on platform (e.g `source venv/bin/activate` for linux and `venv/Scripts/Activate.ps1` for windows)
2. Set variables
   Copy `.env.example` to `.env` and fill the field given, change content inside `consts.py` to fit your server
3. Installing
   After setting up environment, you need to install library required for bot. To do this, run:
   ```.sh
   pip install -r requriements.txt
   ```
4. Running
   Congratulations, you managed to set up my bot, the last step is run `python main.py`. You might want to set scheduler to set auto restart & stuff
