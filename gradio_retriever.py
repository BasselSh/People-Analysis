import requests
import time
import urllib3
from datetime import datetime


class Retriever:
    def __init__(self):
        self.id2photos = dict()
        self.access_token = #Secret
        self.version = "5.131"
        self.group_folder = None

    def get_vk_group_members_one_round(self, group_id):
        self.group_folder = group_id
        with open('ids.txt', 'w') as f:
            pass
        all_ids = []
        offset = 1000
        cnt = 0
        retries = 15
        cond2 = False
        while True:
                        #for large groups: https://api.vk.com/method/groups.getMembers?group_id=GROUP_ID&offset=1000&access_token=YOUR_ACCESS_TOKEN&v=5.131
            group_url = f'https://api.vk.com/method/groups.getMembers?group_id={group_id}&offset={offset}&access_token={self.access_token}&v={self.version}'
            offset += 1000
            response = self.read_url(group_url)
            if response is None or "error" in response:
                cnt +=1
                if (cnt >=retries and cond2):
                    break
                continue
            else:
                cnt = 0

            ids = response["response"]["items"]
            if not ids:
                break
            with open('ids.txt', 'a') as f:
                to_write = ' '.join([str(i) for i in ids])
                f.write(to_write)
                f.write('\n')
            all_ids.extend(ids)
            if len(ids) < 1000:
                cond2 = True
                continue
            else: 
                cond2 = False
        print("IDS LENGTH try", len(all_ids))
        return list(map(str, all_ids))
    
    def get_vk_group_members(self, group_id):
        mx = 0
        ids_max = []
        for i in range(2):
            ids = self.get_vk_group_members_one_round(group_id)
            if ids is None:
                continue
            if len(ids) > mx:
                mx = len(ids)
                ids_max = ids
        print("FINAL IDS LENGTH", len(ids_max))
        return ids_max
        
    # Function to fetch photos from VK profile
    def get_vk_photos(self, profile_id):
        
        url = f"https://api.vk.com/method/photos.get?owner_id={profile_id}&album_id=profile&access_token={self.access_token}&v={self.version}"
        
        print("getting urls")
        response = self.read_url(url)
        if response is None:
            return None, None
        if "error" in response:
            return "Error: " + response["error"]["error_msg"], None
        
        photos = response["response"]["items"]
        photo_urls = [photo["sizes"][-1]["url"] for photo in photos]  # Get largest size photo
        self.id2photos[profile_id] = photo_urls
        if len(photo_urls) == 0:
            return "Error: No photos found", None
        
        return photo_urls[-1], self.id2photos

    def get_user_last_seen(self, user_id):
        url = f"https://api.vk.com/method/users.get?user_ids={user_id}&fields=last_seen,online&access_token={self.access_token}&v={self.version}"
        
        response = self.read_url(url)
        
        if "error" in response:
            return "Error: " + response["error"]["error_msg"], None
        
        user_info = response["response"][0]
        
        if "last_seen" in user_info:
            last_seen_time = datetime.fromtimestamp(user_info['last_seen']['time'])
            online_status = "Online" if user_info['online'] == 1 else "Offline"
            time_difference = int((last_seen_time.date()- datetime.today().date()).days)
            return time_difference, online_status
        else:
            return "User's last seen info not available.", None
        
    def get_user_sex_and_name(self, user_id):
        url = f"https://api.vk.com/method/users.get?user_ids={user_id}&fields=sex&access_token={self.access_token}&v={self.version}"
        
        response = self.read_url(url)
        
        if "error" in response:
            return "Error: " + response["error"]["error_msg"], None, None, None
        
        user_info = response["response"][0]
        if user_info['sex'] == 1:
            gender = "Female"
        elif user_info['sex'] == 2:
            gender = "Male"
        else:
            gender = "Not specified"
        
        return user_info['first_name'], user_info['last_name'], gender, True

        
    def read_url(self, url):
        retries = 10
        for i in range(1, retries):
            try:
                response = requests.get(url)
                response.raise_for_status()  # Check if the request was successful
                return response.json()
            except requests.exceptions.RequestException as e:
                if i == retries - 1:
                    return None
                time.sleep((2 ** i))
            except requests.exceptions.ConnectionError as e:
                if i == retries - 1:
                    return None
                time.sleep((2 ** i))
        return None
