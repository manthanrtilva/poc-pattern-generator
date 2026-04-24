use http_body_util::BodyExt;
use rand::prelude::IndexedRandom;
use serde_json::{Value, json};
use vercel_runtime::{Error, Request, Response, ResponseBody, run, service_fn};

#[tokio::main]
async fn main() -> Result<(), Error> {
    let service = service_fn(handler);
    run(service).await
}

pub async fn handler(req: Request) -> Result<Response<ResponseBody>, Error> {
    let (_, body) = req.into_parts();
    let body_bytes = body.collect().await?.to_bytes();
    let body: Value = serde_json::from_slice(&body_bytes).unwrap_or(json!({}));
    let mut bytes: Vec<u8> = Vec::new();
    let leds = body["leds"].as_u64().unwrap_or(0);
    bytes.extend_from_slice(&(leds as u32).to_be_bytes());
    if let Value::Array(rows) = &body["rows"] {
        for (i, row) in rows.iter().enumerate() {
            let delay = row["delay"].as_u64().unwrap_or(0);
            let colors: Vec<u32> = row["colors"]
                .as_array()
                .map(|arr| arr.iter().filter_map(|v| v.as_u64().map(|n| n as u32)).collect())
                .unwrap_or_default();
            let mut other: Vec<u8> = colors.iter()
                .flat_map(|c| { let b = c.to_be_bytes(); [b[1], b[2], b[3]] })
                .collect();
            bytes.append(&mut other);
            bytes.extend_from_slice(&(delay as u32).to_be_bytes());
            println!("Row {}: delay={}, bytes={:02X?}", i, delay, other);
        }
    }
    println!("leds={}, bytes={:02X?}", leds, bytes);
    Ok(Response::builder()
        .status(200)
        .header("Content-Type", "application/octet-stream")
        .header("Content-Disposition", "attachment; filename=\"pattern.bin\"")
        .body(ResponseBody::from(bytes))?)
}

pub fn choose_starter() -> String {
    let pokemons = ["Bulbasaur", "Charmander", "Squirtle", "Pikachu"];
    let starter = pokemons.choose(&mut rand::rng()).unwrap();
    starter.to_string()
}