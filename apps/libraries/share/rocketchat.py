from rocketchat.api import RocketChatAPI

class RocketChat():
    def __init__(self, token , user_id, domain, room_id):
        self.api = RocketChatAPI(settings={'token': token, 'user_id': user_id, 'domain': domain})
        self.room_id = room_id
    def share(self, file, description, message, mime_type="image/jpeg"):
        self.api.upload_file(self.room_id, file, description, message, mime_type=mime_type)
