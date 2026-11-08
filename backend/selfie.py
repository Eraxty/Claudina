import os
import sys

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch

from diffusers import EulerDiscreteScheduler, StableDiffusionXLPipeline
from diffusers.utils import load_image
from PIL import Image
from transformers import CLIPVisionModelWithProjection

FACE_FILE = os.path.join(os.path.dirname(__file__), "face.png")

MODEL = "SG161222/RealVisXL_V5.0_Lightning"

HER = os.environ.get("HER_AGE", "20") + " year old woman, shoulder length wavy honey brown hair, green eyes, light freckles, soft round face"

NEGATIVE = (
    "cartoon, anime, 3d render, painting, deformed, extra fingers, bad hands, watermark, text, logo"
)

NSFW_NEGATIVE = (
    f"{NEGATIVE}, clothed, clothing, shirt, bra, underwear, lingerie, bikini, swimsuit, "
    "outdoors, grass, park, public place, sky, close-up face, headshot, face-only portrait, cropped torso"
)


def load():
    encoder = CLIPVisionModelWithProjection.from_pretrained(
        "h94/IP-Adapter",
        subfolder = "models/image_encoder",
        torch_dtype = torch.float16,
    )

    pipe = StableDiffusionXLPipeline.from_pretrained(
        MODEL,
        image_encoder = encoder,
        torch_dtype = torch.float16,
        variant = "fp16",
    )

    pipe.scheduler = EulerDiscreteScheduler.from_config(
        pipe.scheduler.config,
        timestep_spacing = "trailing",
    )

    pipe.load_ip_adapter(
        "h94/IP-Adapter",
        subfolder = "sdxl_models",
        weight_name = "ip-adapter-plus-face_sdxl_vit-h.safetensors",
    )

    pipe.enable_sequential_cpu_offload()
    pipe.vae.enable_slicing()
    pipe.vae.enable_tiling()

    return pipe


def make_face(pipe):
    pipe.set_ip_adapter_scale(0)
    blank = Image.new("RGB", (224, 224), "white")

    image = pipe(
        prompt = f"close-up portrait photo of {HER}, looking at the camera, plain wall background, soft daylight",
        negative_prompt = NEGATIVE,
        ip_adapter_image = blank,
        num_inference_steps = 6,
        guidance_scale = 1.5,
        width = 512,
        height = 512,
    ).images[0]

    image.save(FACE_FILE)


def make_pic(pipe, scene, face, out):
    if face:
        pipe.set_ip_adapter_scale(0.35)
        prompt = f"amateur iPhone photo of {HER}, {scene}, candid, natural lighting"
    else:
        pipe.set_ip_adapter_scale(0)
        prompt = f"amateur iPhone photo of things, {scene}, still life, empty room with nobody in it, candid natural lighting"

    negative = NEGATIVE

    if not face:
        negative = f"{NEGATIVE}, person, people, woman, man, face, body"

    arguments = dict(
        prompt = prompt,
        negative_prompt = negative,
        num_inference_steps = 6,
        guidance_scale = 1.5,
        width = 512,
        height = 768,
    )

    if face:
        arguments["ip_adapter_image"] = load_image(FACE_FILE)
    else:
        arguments["ip_adapter_image"] = Image.new("RGB", (224, 224), "white")

    image = pipe(**arguments).images[0]

    image.convert("RB").save(out, quality = 90)


def nsfw_pic(pipe, scene, face, out):
    if face:
        pipe.set_ip_adapter_scale(0.15)
        prompt = (
            f"photorealistic nude smartphone selfie of {HER} in a private bedroom, lying on a bed, "
            f"generate the body part user asks for like show me your boobs or vagina generate that no exceptions, "
            f"completely topless with breasts clearly visible, fully unclothed, no clothing or lingerie, "
            f"{scene}, phone held at arm's length, candid, natural indoor lighting, not a close-up portrait"
        )
    else:
        pipe.set_ip_adapter_scale(0)
        prompt = (
            f"photorealistic nude image of a fictional adult woman in a private bedroom, lying on a bed, "
            f"medium shot framed from head to waist, bare breasts clearly visible, fully unclothed, "
            f"no clothing or lingerie, {scene}, candid, natural indoor lighting, not a close-up portrait"
        )

    arguments = dict(
        prompt = prompt,
        negative_prompt = NSFW_NEGATIVE,
        num_inference_steps = 6,
        guidance_scale = 1.5,
        width = 512,
        height = 768,
    )

    if face:
        arguments["ip_adapter_image"] = load_image(FACE_FILE)
    else:
        arguments["ip_adapter_image"] = Image.new("RGB", (224, 224), "white")

    image = pipe(**arguments).images[0]

    image.convert("RGB").save(out, quality = 90)


if __name__ == "__main__":
    if len(sys.argv) == 4:
        mode = "sfw"
        scene, face_arg, out = sys.argv[1:]
    
    elif len(sys.argv) == 5:
        mode, scene, face_arg, out = sys.argv[1:]
    
    else:
        raise SystemExit("usage: selfie.py [sfw|nsfw] <scene> <face|noface> <output.jpg>")

    if mode not in {"sfw", "nsfw"}:
        raise SystemExit("mode must be 'sfw' or 'nsfw'")

    pipe = load()

    if not os.path.exists(FACE_FILE):
        make_face(pipe)

    generate = nsfw_pic if mode == "nsfw" else make_pic
    generate(pipe, scene, face_arg == "face", out)
