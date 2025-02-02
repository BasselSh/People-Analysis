import gradio as gr
from PIL import Image
import os
from pathlib import Path
import requests
from io import BytesIO 
import pandas as pd
from gradio_retriever import Retriever
import pandas as pd
import time
from tqdm import tqdm
from lavis.models import load_model_and_preprocess
import torch
import shutil

IDS = "180145628\n \
9208295\n \
21136698\n \
 \
" 
'''
180145628
9208295
21136698
279174107
'''


class Processor(Retriever):
    def __init__(self):
        super().__init__()
        self.device = torch.device("cpu")
        self.model, self.vis_processors, self.txt_processors = load_model_and_preprocess(name="blip_vqa", model_type="vqav2", is_eval=True, device=self.device)
# ask a random question.
        self.ids = []
        self.profile_urls = []
        self.labels = []
        self.id_n = 0
        self.status = 'Online'
        self.last_seen = 21 #number of days since it was online
        self.ROOT = Path(__file__).parent
        self.current_image = None
        self.current_image_pil = None
        
    def predict_question(self, question):
        question = self.txt_processors["eval"](question)
        ans = self.model.predict_answers(samples={"image": self.current_image, "text_input": question}, inference_method="generate")[0]
        return ans
    def extract_ids(self, textbox):
        ids = list(map(int, textbox.split('\n')))
        return ids
    
    def _preprocess_image(self, image):
        image = self.vis_processors["eval"](image).unsqueeze(0).to(self.device)
        return image
    
    def read_img(self, url):
        self.current_image = None
        self.current_image_pil = None
        retries = 5
        for i in range(1, retries):
            try:
                response = requests.get(url)
                img_byte = BytesIO(response.content)
                img = Image.open(img_byte)
                if img is None:
                    return
                img = img.convert('RGB')
                self.current_image_pil = img
                img = self._preprocess_image(img)
                self.current_image = img
                return
            except requests.exceptions.RequestException as e:
                if i == retries - 1:
                    img_byte = None
                    break
                time.sleep((2 ** i))
    
    def update_profile(self, group_path, photos, id_name, sex):
            
        for photo_url in photos[::-1]:
            self.read_img(photo_url)
            if self.current_image is None:
                continue
            many_people = self.predict_question("What there more than one person in the image?")
            if many_people == 'yes':
                continue
            else:
                real_person = self.predict_question("Is there a real person in the image?")
                if real_person == 'no':
                    continue
                rich = self.predict_question("Is this person rich?")
                sexy = 'no'
                if sex == 'Female':
                    sexy = self.predict_question("Is this woman sexy?")
                watch = self.predict_question("Is this person wearing a hand watch?")
                earings = self.predict_question("Is this person wearing earrings?")
                necklace = self.predict_question("Is this person wearing a necklace?")
                sunglasses = self.predict_question("Is this person wearing sunglasses?")
                suit = self.predict_question("Is this person wearing a suit?")
                dress = self.predict_question("Is this person wearing a dress?")
                gold = self.predict_question("Is this person wearing gold?")
                in_car = self.predict_question("Is this person in a car?")
                next_car = self.predict_question("Is this person standing next to a car?")
                if rich == 'no' and sexy == 'no' and watch == 'no' and earings == 'no' and necklace == 'no' and sunglasses == 'no' and suit == 'no' and dress == 'no' and gold == 'no' and in_car == 'no' and next_car == 'no':
                    self.current_image_pil.save(f'{group_path}/normal/{id_name}.jpg')
                    return 0
                else:
                    attribues = [watch, sexy, earings, necklace, sunglasses, suit, dress, next_car]
                    self.current_image_pil.save(f'{group_path}/rich/{id_name}.jpg')
                    score = 4 if rich == 'yes' else 0
                    if gold == 'yes':
                        score += 2
                    if in_car == 'yes':
                        score += 2
                    for attribute in attribues:
                        if attribute == 'yes':
                            score += 1
                    print(f'Rich: {score}')
                    return score

        print("Not Recognized")
        return -1

    def update_all_profiles(self, group_path, profile_ids):
        richs = 0
        normals = 0
        nos = 0
        progress = gr.Progress(0)
        if isinstance(profile_ids, str):
            ids = self.extract_ids(profile_ids)
        else:
            ids = profile_ids
        open(group_path / 'all_ids.txt', 'w').write('\n'.join(map(str, ids)))
        if 'current_id.txt' in os.listdir(group_path):
            id_cnt = int(open(group_path / 'current_id.txt', 'r').read())
            table = pd.read_csv(group_path / 'profile_table.csv')
        else:
            id_cnt = 0
            table = pd.DataFrame(columns=['Profile ID', 'Name', 'Surname', 'Link', 'Sex', 'Rich'])

        for id in progress.tqdm(ids, desc="Analyzing Images"):
            name, surname, sex, cond = self.get_user_sex_and_name(id)
            if cond is None:
                print("ID Not found")
                continue
            # if self.status == "Online" and status == "Offline":
            #     print("Skipping offline user")
            #     continue
            # if active_days > self.last_seen:
                # print("Skipping user with inactive days")
                # continue
            print("PROFILE ID", id)
            profile_url, id2photos = self.get_vk_photos(id)
            if id2photos is None:
                print("No photos")
                continue
            
            label = self.update_profile(group_path, id2photos[id], str(id), sex)
            if label == -1:
                nos += 1
            elif label == 0:
                normals += 1
            else:
                richs += 1
            link = f"vk.com/id{str(id)}"
            table.loc[id_cnt] = [id, name, surname, link, sex, int(label)]
            if id_cnt%10==0 and id_cnt != 0:
                self.save_table(group_path, table)
                with open(group_path / 'current_id.txt', 'w') as f:
                    f.write(str(id_cnt))
                stats = pd.DataFrame({'pred': ['Normal', 'Rich', 'Not Recognized'], 'count': [normals, richs, nos]})
                stats.to_csv(group_path / 'stats.csv', index=False)
                
            
            id_cnt += 1

        self.save_table(group_path, table)
        stats = pd.DataFrame({'pred': ['Normal', 'Rich', 'Not Recognized'], 'count': [normals, richs, nos]})
        stats.to_csv(group_path / 'stats.csv', index=False)

        with open(group_path / 'finished.txt', 'w') as f:
            f.write('done')
        dropdown, bar, select_online, rich_table = self.update_analysis_tab()
        return dropdown, bar, select_online, rich_table 
    
    def save_table(self, group_path, table):
        table.to_csv(group_path / 'profile_table.csv')
        
    def update_all_profiles_from_group(self, group_id):
        group_name = group_id
        group_path = self.ROOT / 'datasets' / group_name
        os.makedirs(group_path, exist_ok=True)
        if 'finished.txt' in os.listdir(group_path):
            return self.update_analysis_tab()
        else:
            if 'all_ids.txt' in os.listdir(group_path):
                ids = list(map(int, open(group_path / 'all_ids.txt', 'r').read().split('\n')))
            else:
                shutil.rmtree(group_path)
                os.makedirs(group_path, exist_ok=True)
                os.makedirs(f'{group_path}/rich', exist_ok=True)
                os.makedirs(f'{group_path}/normal', exist_ok=True)
                ids = self.get_vk_group_members(group_id)
            return self.update_all_profiles(group_path, ids)

    # def update_all_profiles_from_file(self, file):
    #     df = pd.read_csv(file)
    #     ids = df.iloc[:, 0].tolist()
    #     group_path = self.ROOT / 'datasets' / 'temp'
    #     os.makedirs(group_path, exist_ok=True)
    #     return gr.Label(label="Group added"), self.update_all_profiles(group_path, ids)

    def download_table(self, table):
        path = 'table_temp.csv'
        table.to_csv(path)
        return path

    def show_online_rich_users(self, group_id):
        group_path = self.ROOT / 'datasets' / group_id
        table = pd.read_csv(group_path / 'profile_table.csv')
        mask = [str(status) != 'Not Recognized' and str(status) != '0' for status in table['Rich']]
        table = table[mask]
        rich_users =  table['Profile ID'].tolist()
        online_rich_users = pd.DataFrame(columns=['Profile ID','Name','Surname','Link','Sex','Rich'])
        progress = gr.Progress(0)
        for i, user in enumerate(progress.tqdm(rich_users, desc="Analyzing Images")):
            id = user
            active_days, status = self.get_user_last_seen(id)
            if status is None:
                print("ID Not found")
                continue
            if status == "Online":
                print("User is online")
                online_rich_users.loc[i] = table.iloc[i]
        return online_rich_users
    
    def get_available_groups(self):
        path = self.ROOT / 'datasets'
        all_groups = os.listdir(path)
        return [group for group in all_groups if 'profile_table.csv' in os.listdir(path / group)]
    def update_analysis_tab(self):
        groups = self.get_available_groups()
        default_group = groups[0] if groups else None
        dropdown = gr.Dropdown(label='Group ID', choices=groups, value=default_group)
        # stats = pd.read_csv('datasets/cccp_fitness/rich_stats.csv')
        # bar = gr.BarPlot(stats, x='pred', y='count', x_title='Pred', y_title='Count')
        bar, table_df = processor.get_group_stats_and_table(default_group)
        if bar is None:
            bar = gr.BarPlot(pd.DataFrame(), x='pred', y='count', x_title='Pred', y_title='Count')
        select_online = gr.Button("Select Online")
        # bar = gr.BarPlot(x=stats.iloc[0].to_list(), y=stats.columns.to_list())
        rich_table = gr.DataFrame(table_df)
        self.rich_table = rich_table
        return dropdown, bar, select_online, rich_table

    
    def get_group_stats_and_table(self, group_id):
        if group_id is None:
            return None, None
        group_path = self.ROOT / 'datasets' / group_id
        stats_table = pd.read_csv(group_path / 'stats.csv')
        pred = stats_table['pred'].to_list()
        count = stats_table['count'].to_list()
        stats = pd.DataFrame({'pred': pred, 'count': count})
        bar = gr.BarPlot(stats, x='pred', y='count', x_title='Prediction', y_title='Count')
        table = pd.read_csv(group_path / 'profile_table.csv')
        mask = [str(status) != 'Not Recognized' and str(status) != '0' for status in table['Rich']]
        table = table[mask]
        return bar, table
    
processor = Processor()
with gr.Blocks() as demo:
    with gr.Tab("Add new group"):
        # file = gr.File(label='ids file', file_types=['csv'])
        search = gr.Textbox(label='Group ID')#value=IDS)
        submit = gr.Button("Add group")
        status = gr.Label(label="")

    with gr.Tab("Analyze group"):
        dropdown, bar, select_online, rich_table = processor.update_analysis_tab()
        download_bn = gr.Button("Download Table")
        download = gr.File()
    # Logic to combine the image input and button click as inputs
    submit.click(processor.update_all_profiles_from_group, inputs=search, outputs=[status, dropdown, bar, select_online, rich_table])
    # file.upload(processor.update_all_profiles_from_file, inputs=file, outputs=[table])
    download_bn.click(processor.download_table, inputs=rich_table, outputs=[download])
    dropdown.select(processor.get_group_stats_and_table, inputs=dropdown, outputs=[bar, rich_table])
    select_online.click(processor.show_online_rich_users, inputs=dropdown, outputs=[rich_table])


demo.launch()#share=True

#cccp_fitness
