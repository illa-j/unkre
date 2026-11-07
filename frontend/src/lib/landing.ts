import { creationHref } from "./creation-intent";

export const landingPresets = [
  { id: "natural-portrait", label: "Natural light", model: "Qwen Image 2.1", image: "/images/qwen-image-2-1/example.png", width: 2048, height: 3072, alt: "Ultra-realistic Qwen model example with silver and mint hair, natural skin texture and soft daylight", prompt: "An adult woman with silver and mint hair, a denim top and delicate jewelry. A candid portrait in soft window light, natural skin texture, realistic detail and a quiet afternoon mood." },
  { id: "studio-portrait", label: "Gothic glamour", model: "Krea 2 Turbo", image: "/images/krea-2-turbo-gothic.png", width: 384, height: 512, alt: "Krea 2 Turbo model example of a woman with long black hair and dark makeup in a bright glass conservatory", prompt: "A glamorous gothic portrait of an adult woman with long black hair, blunt bangs, dark lips and smoky eye makeup, wearing a black top and a lace choker with layered silver chains. She stands in a bright glass conservatory with white steel arches, soft daylight and realistic skin texture. A bold, ultra-realistic fashion photograph." },
] as const;

export const referenceHref = creationHref({ model: "Qwen Image 2.1", reference: true });
export const characterHref = creationHref({ model: "Krea 2", prompt: "An adult woman with long dark hair, a black and white outfit, a relaxed expression and natural features. A candid photograph at a colorful night market.", seed: "104729" });
