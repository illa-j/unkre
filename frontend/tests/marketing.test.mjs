import assert from "node:assert/strict";
import { test } from "node:test";
import { studioDestination, creationHref, resolveCreationModel, supportsReferenceImages } from "../src/lib/creation-intent.ts";
import { validAnalyticsPayload } from "../src/lib/analytics.ts";

test("creation presets survive sign-in without permitting external redirects", () => {
  const href = creationHref({model:"Qwen Image 2.1",prompt:"A portrait & a new scene",lora:"Natural look",seed:"42",reference:true});
  assert.equal(studioDestination(href), href);
  const parsed = new URL(href,"https://unkre.com");
  assert.equal(parsed.searchParams.get("prompt"),"A portrait & a new scene");
  assert.equal(parsed.searchParams.get("reference"),"1");
  assert.equal(studioDestination("/studio/credits"),"/studio/credits");
  for(const unsafe of ["https://evil.example/", "//evil.example/studio", "/studio\\evil", "/studio/../../outside", "/studios", "/studio\r\nLocation: evil",null]) assert.equal(studioDestination(unsafe),"/studio");
  assert.equal(studioDestination("/studio?next=https://evil.example&model=qwen"),"/studio?model=qwen");
});

test("creation presets keep multiple LoRA ids", () => {
  const href = creationHref({ model: "Krea 2 Turbo", lora: ["id-1", "id-2"] });
  const parsed = new URL(href, "https://unkre.com");
  assert.equal(parsed.searchParams.get("lora"), "id-1,id-2");
  assert.equal(studioDestination(href), href);
  assert.equal(studioDestination(href.replace("id-1,id-2", "id-1,id-2,id-3,id-4")), href.replace("id-1,id-2", "id-1,id-2,id-3,id-4"));
});

test("analytics only accepts defined funnel events and never carries prompts or identity", () => {
  assert.deepEqual(validAnalyticsPayload({event:"generation_completed",placement:"studio",path:"/studio",device:"mobile",prompt:"private prompt",file:"private photo",user_id:"123",email:"private@example.com"}),{event:"generation_completed",placement:"studio",path:"/studio",device:"mobile"});
  assert.equal(validAnalyticsPayload({event:"anything"}),null);
  assert.equal(validAnalyticsPayload({event:"cta_click",path:"/studio?prompt=private"}),null);
  assert.equal(validAnalyticsPayload({event:"cta_click",placement:"<script>"}),null);
});

test("web vitals accept numeric measurements without forwarding performance entry details", () => {
  assert.deepEqual(validAnalyticsPayload({event:"web_vital",metric:"LCP",value:1240.5,path:"/",entries:[{url:"private"}]}),{event:"web_vital",metric:"LCP",value:1240.5,path:"/"});
  assert.equal(validAnalyticsPayload({event:"web_vital",metric:"URL",value:1}),null);
  assert.equal(validAnalyticsPayload({event:"web_vital",metric:"CLS",value:-1}),null);
});


test("preset model selection does not silently substitute a different workflow", () => {
  const models=[{id:"qwen-id",name:"Qwen Image 2.1"},{id:"krea-id",name:"Krea 2 Turbo"}];
  assert.equal(resolveCreationModel(models,"qwen-id"),models[0]);
  assert.equal(resolveCreationModel(models,"Qwen Image 2.1"),models[0]);
  assert.equal(resolveCreationModel(models,"Krea 2"),models[1]);
  assert.equal(resolveCreationModel(models,"Unavailable model"),undefined);
  assert.equal(resolveCreationModel(models,""),models[0]);
});

test("reference uploads require the resolved Qwen Image 2.1 model", () => {
  assert.equal(supportsReferenceImages({name:"Qwen Image 2.1"}),true);
  assert.equal(supportsReferenceImages({name:"  qWeN iMaGe 2.1  "}),true);
  for (const name of ["Krea 2", "Qwen", "Qwen Image 2", "Qwen Image 2.1 Turbo", "Other Qwen Image 2.1"]) {
    assert.equal(supportsReferenceImages({name}),false,name);
  }
  assert.equal(supportsReferenceImages(undefined),false);
});
