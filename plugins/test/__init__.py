import cinShared

async def test_command(message):
    await message.channel.send("yo")

def bind_commands():
     return {
         "test": test_command
     }

def bind_commands():
     return {
         "test": "test command"
     }