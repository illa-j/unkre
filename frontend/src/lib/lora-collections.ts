export type LoraExample = {
  file: string;
  width: number;
  height: number;
};

export type LoraCollection = {
  id: string;
  name: string;
  model: "Krea 2" | "Qwen Image 2.1";
  source?: string;
  sfw: LoraExample[];
  nsfw: LoraExample[];
  mixedLayout?: boolean;
};

export const loraCollections: LoraCollection[] = [
  {
    id: "realistic-snapshot",
    name: "Realistic Snapshot",
    model: "Krea 2",
    source: "https://civitai.red/models/2268008/realistic-snapshot-moss-image-krea2-zit?modelVersionId=3371723",
    sfw: [
      { file: "realistic-snapshot-sfw-1", width: 1080, height: 1920 },
      { file: "realistic-snapshot-sfw-2", width: 1072, height: 1904 },
    ],
    nsfw: [
      { file: "realistic-snapshot-nsfw-1", width: 1088, height: 1928 },
      { file: "realistic-snapshot-nsfw-2", width: 1088, height: 1928 },
    ],
  },
  {
    id: "mystic-xxx",
    name: "[KREA 2] Mystic XXX",
    model: "Krea 2",
    sfw: [],
    nsfw: [
      { file: "mystic-xxx-nsfw-1", width: 1224, height: 1632 },
      { file: "mystic-xxx-nsfw-2", width: 3328, height: 2496 },
    ],
    mixedLayout: true,
  },
  {
    id: "lenovo-ultrareal",
    name: "Lenovo UltraReal",
    model: "Krea 2",
    sfw: [{ file: "lenovo-ultrareal-1", width: 1088, height: 1920 }],
    nsfw: [],
  },
  {
    id: "nicegirls-ultrareal",
    name: "NiceGirls UltraReal",
    model: "Krea 2",
    sfw: [
      { file: "nicegirls-ultrareal-1", width: 450, height: 675 },
      { file: "nicegirls-ultrareal-2", width: 450, height: 594 },
    ],
    nsfw: [],
  },
  {
    id: "qwen-lenovo-ultrareal",
    name: "Lenovo UltraReal",
    model: "Qwen Image 2.1",
    sfw: [
      { file: "qwen-lenovo-ultrareal-sfw-1", width: 1088, height: 1440 },
      { file: "qwen-lenovo-ultrareal-sfw-2", width: 2048, height: 3072 },
    ],
    nsfw: [],
  },
  {
    id: "qwen-nicegirls-ultrareal",
    name: "NiceGirls UltraReal",
    model: "Qwen Image 2.1",
    sfw: [
      { file: "qwen-nicegirls-ultrareal-sfw-1", width: 1776, height: 1184 },
      { file: "qwen-nicegirls-ultrareal-sfw-2", width: 896, height: 1184 },
    ],
    nsfw: [],
  },
  {
    id: "qwen-femaledvaginus-nsfw",
    name: "FemaledVaginus-NSFW",
    model: "Qwen Image 2.1",
    sfw: [],
    nsfw: [
      { file: "qwen-femaledvaginus-nsfw-1", width: 1536, height: 2048 },
      { file: "qwen-femaledvaginus-nsfw-2", width: 450, height: 681 },
    ],
  },
];
