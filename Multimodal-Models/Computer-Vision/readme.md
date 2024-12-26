# Microsoft Computer Vision Test

I have developed a Python program that runs on Windows and utilizes Azure Computer Vision (Azure CV) .

- Perform object recognition on images selected by the user. After the recognition is complete, the user can choose the objects they wish to retain (one or more). The selected objects are then cropped and saved locally.
- Do background remove based on the images and the object user select.



**Object detection and image segmentation**：

***Please click below pictures to see my demo vedio on Yutube***:
[![CV-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/edjB-PDapN8)

Currently, the background removal API of Azure CV has been discontinued. In the future, this functionality can be achieved through the region-to-segmentation feature of Florence-2. For detailed implementation, please refer to: https://huggingface.co/microsoft/Florence-2-large/blob/main/sample_inference.ipynb



**Object recognition and background remove：**

***Please click below pictures to see my demo vedio on Yutube***:
[![CV2-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/6x49D3YUTGA)

## **Code for Object detection and image segmentation**



```
import requests  
from PIL import Image, ImageTk, ImageDraw  
import tkinter as tk  
from tkinter import messagebox, filedialog  
import threading  
  
# Azure Computer Vision API 信息  
subscription_key = "o"  
endpoint = "https://cv-2.cognitiveservices.azure.com/"  
  
# 图像分析函数  
def analyze_image(image_path):  
    analyze_url = endpoint + "vision/v3.2/analyze"  
    headers = {  
        'Ocp-Apim-Subscription-Key': subscription_key,  
        'Content-Type': 'application/octet-stream'  
    }  
    params = {'visualFeatures': 'Objects'}  
  
    try:  
        with open(image_path, 'rb') as image_data:  
            response = requests.post(  
                analyze_url, headers=headers, params=params,  
                data=image_data, timeout=10  # 设置超时时间为10秒  
            )  
            response.raise_for_status()  
            analysis = response.json()  
        print("图像分析完成")  
        return analysis  
    except requests.exceptions.Timeout:  
        print("请求超时，请检查网络连接或稍后重试。")  
        messagebox.showerror("错误", "请求超时，请检查网络连接或稍后重试。")  
    except Exception as e:  
        print("在 analyze_image 中发生异常：", e)  
        messagebox.showerror("错误", f"发生错误：{e}")  
  
# 背景移除函数  
def remove_background(image_path, objects_to_keep):  
    print("remove_background 被调用")  
    try:  
        image = Image.open(image_path).convert("RGBA")  
        width, height = image.size  
  
        # 创建一个透明背景的图像  
        new_image = Image.new("RGBA", image.size, (0, 0, 0, 0))  
  
        # 创建一个与图像大小相同的掩码  
        mask = Image.new("L", (width, height), 0)  
        draw = ImageDraw.Draw(mask)  
  
        # 在掩码上绘制要保留的对象区域  
        for obj in objects_to_keep:  
            x1, y1, x2, y2 = obj['coords']  
            # 将坐标转换为整数  
            x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])  
            # 绘制矩形区域，填充为白色（表示保留）  
            draw.rectangle([x1, y1, x2, y2], fill=255)  
  
        # 应用掩码到原始图像上  
        new_image.paste(image, (0, 0), mask)  
  
        print("背景移除完成，显示结果")  
        new_image.show()  
  
        # 保存结果  
        save_path = filedialog.asksaveasfilename(  
            defaultextension=".png",  
            filetypes=[('PNG 图像', '*.png')],  
            title='保存结果图像'  
        )  
        if save_path:  
            new_image.save(save_path)  
            messagebox.showinfo("信息", f"处理完成，结果已保存到：{save_path}")  
  
    except Exception as e:  
        print("在 remove_background 中发生异常：", e)  
        messagebox.showerror("错误", f"发生错误：{e}")  
    print("remove_background 完成")  
  
# GUI 界面  
def create_gui():  
    # 创建主窗口  
    root = tk.Tk()  
    root.title("选择要保留的对象")  
  
    # 添加选择图像的按钮  
    def select_image():  
        image_path = filedialog.askopenfilename(  
            title='选择一张图像',  
            filetypes=[('图像文件', '*.png;*.jpg;*.jpeg;*.bmp'), ('所有文件', '*.*')]  
        )  
        if image_path:  
            show_image(image_path)  
        else:  
            messagebox.showwarning("警告", "未选择图像文件。")  
  
    def show_image(image_path):  
        analysis = analyze_image(image_path)  
        if analysis is None:  
            print("分析结果为空，无法创建 GUI")  
            return  
  
        # 加载图像  
        pil_image = Image.open(image_path)  
        img_width, img_height = pil_image.size  
        tk_image = ImageTk.PhotoImage(pil_image)  
  
        # 创建 Canvas  
        canvas = tk.Canvas(root, width=img_width, height=img_height)  
        canvas.pack()  
  
        # 在 Canvas 上显示图像  
        canvas.create_image(0, 0, anchor='nw', image=tk_image)  
        canvas.tk_image = tk_image  # 保留对图像的引用  
  
        # 记录对象的矩形、标签和选择状态  
        object_items = []  
  
        # 处理每个检测到的对象  
        for obj in analysis['objects']:  
            rect = obj['rectangle']  
            x = rect['x']  
            y = rect['y']  
            w = rect['w']  
            h = rect['h']  
            obj_name = obj['object']  
  
            # 绘制对象的边界框  
            rect_item = canvas.create_rectangle(  
                x, y, x + w, y + h,  
                outline='red', width=2  
            )  
  
            # 显示对象名称  
            text_item = canvas.create_text(  
                x + w/2, y - 10,  
                text=obj_name,  
                fill='red'  
            )  
  
            # 将对象的选择状态初始化为未选中  
            selected = False  
  
            # 将对象的信息添加到列表  
            object_items.append({  
                'rect_item': rect_item,  
                'text_item': text_item,  
                'coords': (x, y, x + w, y + h),  
                'object': obj_name,  
                'selected': selected  
            })  
  
        # 定义点击事件处理函数  
        def on_canvas_click(event):  
            for item in object_items:  
                x1, y1, x2, y2 = item['coords']  
                if x1 <= event.x <= x2 and y1 <= event.y <= y2:  
                    # 切换选择状态  
                    item['selected'] = not item['selected']  
                    if item['selected']:  
                        # 已选中，边框设为绿色  
                        canvas.itemconfig(item['rect_item'], outline='green')  
                        canvas.itemconfig(item['text_item'], fill='green')  
                    else:  
                        # 未选中，边框设为红色  
                        canvas.itemconfig(item['rect_item'], outline='red')  
                        canvas.itemconfig(item['text_item'], fill='red')  
                    break  
  
        canvas.bind("<Button-1>", on_canvas_click)  
  
        # 提交按钮  
        def on_submit():  
            print("on_submit 被调用")  
            selected_objects = []  
            for item in object_items:  
                if item['selected']:  
                    # 如果对象被选中，保存其信息  
                    selected_objects.append(item)  
            if not selected_objects:  
                messagebox.showwarning("警告", "请至少选择一个对象。")  
            else:  
                # 调用背景消除函数  
                threading.Thread(target=remove_background, args=(image_path, selected_objects)).start()  
                print("on_submit 完成")  
  
        submit_button = tk.Button(root, text="提交", command=on_submit)  
        submit_button.pack()  
  
    # 添加选择图像的按钮  
    select_button = tk.Button(root, text="选择图像", command=select_image)  
    select_button.pack()  
  
    root.mainloop()  
  
# 示例使用  
if __name__ == "__main__":  
    create_gui()  
```

![imgaes](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Computer-Vision/images/3.png)

## Code for Object recognition and background remove

On GPU VM：

```
from transformers import AutoProcessor, AutoModelForCausalLM  
from PIL import Image, ImageDraw, ImageChops  
import torch  
import numpy as np  
import ipywidgets as widgets  
from IPython.display import display, clear_output  
import io  
  
# Load the model  
model_id = 'microsoft/Florence-2-large'  
device = 'cuda' if torch.cuda.is_available() else 'cpu'  
  
model = AutoModelForCausalLM.from_pretrained(  
    model_id,  
    trust_remote_code=True,  
    torch_dtype='auto'  
).to(device)  
  
processor = AutoProcessor.from_pretrained(  
    model_id,  
    trust_remote_code=True  
)  
  
def run_example(task_prompt, image, text_input=None):  
    if text_input is None:  
        prompt = task_prompt  
    else:  
        prompt = task_prompt + text_input  
  
    # Process inputs  
    inputs = processor(  
        text=prompt,  
        images=image,  
        return_tensors="pt"  
    )  
  
    # Move inputs to the device with appropriate data types  
    inputs = {  
        "input_ids": inputs["input_ids"].to(device),  # input_ids are integers (int64)  
        "pixel_values": inputs["pixel_values"].to(device, torch.float16)  # pixel_values need to be float16  
    }  
  
    with torch.no_grad():  
        generated_ids = model.generate(  
            input_ids=inputs["input_ids"],  
            pixel_values=inputs["pixel_values"],  
            max_new_tokens=1024,  
            early_stopping=False,  
            do_sample=False,  
            num_beams=3,  
        )  
  
    generated_text = processor.batch_decode(  
        generated_ids,  
        skip_special_tokens=False  
    )[0]  
  
    parsed_answer = processor.post_process_generation(  
        generated_text,  
        task=task_prompt,  
        image_size=(image.width, image.height)  
    )  
    return parsed_answer  
  
def create_mask(image_size, prediction):  
    mask = Image.new('L', image_size, 0)  
    mask_draw = ImageDraw.Draw(mask)  
    for polygons in prediction['polygons']:  
        for _polygon in polygons:  
            _polygon = np.array(_polygon).reshape(-1, 2)  
            if len(_polygon) < 3:  
                continue  
            _polygon = _polygon.flatten().tolist()  
            mask_draw.polygon(_polygon, outline=255, fill=255)  
    return mask  
  
def combine_masks(masks):  
    combined_mask = Image.new('L', masks[0].size, 0)  
    for mask in masks:  
        combined_mask = ImageChops.lighter(combined_mask, mask)  
    return combined_mask  
  
def apply_combined_mask(image, combined_mask):  
    # Convert the image to RGBA  
    image = image.convert('RGBA')  
    result_image = Image.new('RGBA', image.size, (255, 255, 255, 0))  
    result_image = Image.composite(image, result_image, combined_mask)  
    return result_image  
  
def process_image_multiple_objects(image, descriptions):  
    """  
    Process the image for multiple object descriptions.  
  
    Parameters:  
    - image: PIL.Image object.  
    - descriptions: list of strings, descriptions of objects to retain.  
  
    Returns:  
    - output_image: Processed image with the specified objects retained.  
    """  
    masks = []  
    for desc in descriptions:  
        print(f"Processing description: {desc}")  
        results = run_example('<REFERRING_EXPRESSION_SEGMENTATION>', image, text_input=desc.strip())  
        prediction = results['<REFERRING_EXPRESSION_SEGMENTATION>']  
        if not prediction['polygons']:  
            print(f"No objects found for description: {desc}")  
            continue  
        # Generate mask for this object  
        mask = create_mask(image.size, prediction)  
        masks.append(mask)  
  
    if not masks:  
        print("No objects found for any of the descriptions.")  
        return image.convert('RGBA')  
  
    # Combine all masks  
    combined_mask = combine_masks(masks)  
  
    # Apply the combined mask  
    output_image = apply_combined_mask(image, combined_mask)  
    return output_image  
  
def on_file_upload(change):  
    # Clear any previous output (except for the upload widget)  
    clear_output(wait=True)  
    display(widgets.HTML("<h3>Please upload an image file using the widget below:</h3>"))  
    display(upload_button)  
  
    # Check if a file has been uploaded  
    if upload_button.value:  
        # Get the first uploaded file  
        uploaded_file = upload_button.value[0]  
  
        # Access the content of the file  
        image_data = uploaded_file.content  
        image = Image.open(io.BytesIO(image_data)).convert('RGB')  
  
        # Display the uploaded image  
        print("Uploaded Image:")  
        display(image)  
  
        # Create a text box for object descriptions  
        desc_box = widgets.Text(  
            value='',  
            placeholder='Enter descriptions of objects to retain, separated by commas',  
            description='Object Descriptions:',  
            disabled=False,  
            layout=widgets.Layout(width='80%')  
        )  
  
        # Create a button to submit the descriptions  
        submit_button = widgets.Button(  
            description='Process Image',  
            disabled=False,  
            button_style='primary',  
            tooltip='Click to process the image',  
            icon='check'  
        )  
  
        # Function to handle the button click  
        def on_submit_button_click(b):  
            object_descriptions = desc_box.value  
            if not object_descriptions.strip():  
                print("Please enter at least one description.")  
                return  
            # Disable the button to prevent multiple clicks  
            submit_button.disabled = True  
            # Clear previous output  
            clear_output(wait=True)  
            print("Processing the image. This may take a few moments...")  
            # Split the descriptions by commas  
            descriptions_list = [desc.strip() for desc in object_descriptions.split(',') if desc.strip()]  
            if not descriptions_list:  
                print("No valid descriptions entered. Exiting the process.")  
                return  
            # Process the image  
            output_image = process_image_multiple_objects(image, descriptions_list)  
            # Display the result  
            display(output_image)  
  
            # Optionally, save the output image  
            # Uncomment the lines below to save the image  
            # output_image.save('output_image.png')  
            # print("The image with background removed has been saved as 'output_image.png'")  
  
        submit_button.on_click(on_submit_button_click)  
  
        # Display the text box and submit button  
        display(widgets.VBox([desc_box, submit_button]))  
  
# Create the upload widget  
upload_button = widgets.FileUpload(  
    accept='image/*',  
    multiple=False  
)  
  
display(widgets.HTML("<h3>Please upload an image file using the widget below:</h3>"))  
display(upload_button)  
  
# Observe changes in the upload widget  
upload_button.observe(on_file_upload, names='value')  
```

![imgaes](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Computer-Vision/images/2.png)

![imgaes](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Computer-Vision/images/1.png)
