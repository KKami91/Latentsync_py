import os
import random
import sys
from typing import Sequence, Mapping, Any, Union
import torch
import runpod
import base64
import torch
from typing import Sequence, Mapping, Any, Union
from io import BytesIO


def get_value_at_index(obj: Union[Sequence, Mapping], index: int) -> Any:
    """Returns the value at the given index of a sequence or mapping.

    If the object is a sequence (like list or string), returns the value at the given index.
    If the object is a mapping (like a dictionary), returns the value at the index-th key.

    Some return a dictionary, in these cases, we look for the "results" key

    Args:
        obj (Union[Sequence, Mapping]): The object to retrieve the value from.
        index (int): The index of the value to retrieve.

    Returns:
        Any: The value at the given index.

    Raises:
        IndexError: If the index is out of bounds for the object and the object is not a mapping.
    """
    try:
        return obj[index]
    except KeyError:
        return obj["result"][index]


def find_path(name: str, path: str = None) -> str:
    """
    Recursively looks at parent folders starting from the given path until it finds the given name.
    Returns the path as a Path object if found, or None otherwise.
    """
    # If no path is given, use the current working directory
    if path is None:
        path = os.getcwd()

    # Check if the current directory contains the name
    if name in os.listdir(path):
        path_name = os.path.join(path, name)
        print(f"{name} found: {path_name}")
        return path_name

    # Get the parent directory
    parent_directory = os.path.dirname(path)

    # If the parent directory is the same as the current directory, we've reached the root and stop the search
    if parent_directory == path:
        return None

    # Recursively call the function with the parent directory
    return find_path(name, parent_directory)


def add_comfyui_directory_to_sys_path() -> None:
    """
    Add 'ComfyUI' to the sys.path
    """
    comfyui_path = "/workspace/ComfyUI"
    if os.path.isdir(comfyui_path):
        sys.path.append(comfyui_path)
        print(f"'{comfyui_path}' added to sys.path")


def add_extra_model_paths() -> None:
    """
    Parse the optional extra_model_paths.yaml file and add the parsed paths to the sys.path.
    """
    try:
        from main import load_extra_path_config
    except ImportError:
        print(
            "Could not import load_extra_path_config from main.py. Looking in utils.extra_config instead."
        )
        from utils.extra_config import load_extra_path_config

    extra_model_paths = find_path("extra_model_paths.yaml")

    if extra_model_paths is not None:
        load_extra_path_config(extra_model_paths)
    else:
        print("Could not find the extra_model_paths config file.")


# add_comfyui_directory_to_sys_path()
# add_extra_model_paths()


def import_custom_nodes() -> None:
    """Find all custom nodes in the custom_nodes folder and add those node objects to NODE_CLASS_MAPPINGS

    This function sets up a new asyncio event loop, initializes the PromptServer,
    creates a PromptQueue, and initializes the custom nodes.
    """
    import asyncio
    import execution
    from nodes import init_extra_nodes
    import server

    # Creating a new event loop and setting it as the default loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Creating an instance of PromptServer with the loop
    server_instance = server.PromptServer(loop)
    execution.PromptQueue(server_instance)

    # Initializing custom nodes
    init_extra_nodes()




def setup_environment():
    """Setup the ComfyUI environment"""
    add_comfyui_directory_to_sys_path()
    add_extra_model_paths()
    import_custom_nodes()


def process_latentsync(video_data: bytes, audio_data: bytes, video_name: str):
    from nodes import NODE_CLASS_MAPPINGS

    # 파일명에서 확장자 제거
    video_name_without_ext = os.path.splitext(video_name)[0]    

    # 임시 파일로 저장
    video_path = "/tmp/input_video.mp4"
    audio_path = "/tmp/input_audio.wav"

    with open(video_path, "wb") as f:
        f.write(video_data)
    with open(audio_path, "wb") as f:
        f.write(audio_data)

    try:
        with torch.inference_mode():
            loadaudio = NODE_CLASS_MAPPINGS["LoadAudio"]()
            loadaudio_37 = loadaudio.load(audio=audio_path)

            vhs_loadvideo = NODE_CLASS_MAPPINGS["VHS_LoadVideo"]()
            vhs_loadvideo_40 = vhs_loadvideo.load_video(
                video=video_path,
                force_rate=25,
                custom_width=512,
                custom_height=512,
                frame_load_cap=0,
                skip_first_frames=0,
                select_every_nth=1,
                format="AnimateDiff",
                unique_id=12015943199208297010,
            )

            d_videolengthadjuster = NODE_CLASS_MAPPINGS["D_VideoLengthAdjuster"]()
            d_latentsyncnode = NODE_CLASS_MAPPINGS["D_LatentSyncNode"]()
            vhs_videocombine = NODE_CLASS_MAPPINGS["VHS_VideoCombine"]()

            output_path = "/tmp/output.mp4"

            d_videolengthadjuster_53 = d_videolengthadjuster.adjust(
                mode="pingpong",
                fps=25,
                silent_padding_sec=0.5,
                images=get_value_at_index(vhs_loadvideo_40, 0),
                audio=get_value_at_index(loadaudio_37, 0),
            )

            d_latentsyncnode_43 = d_latentsyncnode.inference(
                seed=random.randint(1, 2**32 - 1),
                images=get_value_at_index(d_videolengthadjuster_53, 0),
                audio=get_value_at_index(d_videolengthadjuster_53, 1),
            )

            vhs_videocombine_41 = vhs_videocombine.combine_video(
                frame_rate=25,
                loop_count=0,
                filename_prefix="convert_{video_name_without_ext}",
                format="video/h264-mp4",
                pix_fmt="yuv420p",
                crf=19,
                save_metadata=True,
                trim_to_audio=False,
                pingpong=False,
                save_output=True,
                images=get_value_at_index(d_latentsyncnode_43, 0),
                audio=get_value_at_index(d_latentsyncnode_43, 1),
                unique_id=7599875590960303900,
            )

            # 결과 파일 읽기 및 base64 인코딩
            with open(output_path, "rb") as f:
                output_data = f.read()
            
            return base64.b64encode(output_data).decode('utf-8')
    
    finally:
        # 임시 파일 정리
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if os.path.exists(output_path):
            os.remove(output_path)

@runpod.handler
def handler(event):
    """Runpod serverless handler"""
    try:
        # 입력 데이터 검증
        if 'input' not in event or 'video' not in event['input'] or 'audio' not in event['input']:
            raise ValueError("Missing required input fields (video and/or audio)")

        # 입력 데이터 디코딩
        video_data = base64.b64decode(event['input']['video'])
        audio_data = base64.b64decode(event['input']['audio'])
        video_name = event['input']['video_name']
        
        # 환경 설정
        setup_environment()
        
        # 처리
        output_base64 = process_latentsync(video_data, audio_data, video_name)
        
        return {
            "output": {
                "video_data": output_base64,
                "video_name": f"convert_{os.path.splitext(video_name)[0]}.mp4"  # 결과 파일명도 함께 반환
            }
        }
    except Exception as e:
        return {
            "error": str(e)
        }


if __name__ == "__main__":
    runpod.serverless.start({
        "handler": handler
    })