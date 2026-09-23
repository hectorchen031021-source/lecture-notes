import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count > 1 else { exit(1) }
let path = CommandLine.arguments[1]
guard let img = NSImage(contentsOfFile: path),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { exit(2) }

let request = VNRecognizeTextRequest { req, _ in
    guard let obs = req.results as? [VNRecognizedTextObservation] else { return }
    for o in obs {
        if let top = o.topCandidates(1).first {
            print(top.string)
        }
    }
}
request.recognitionLevel = .accurate
request.recognitionLanguages = ["fr-FR", "en-US", "de-DE", "it-IT", "la"]
request.usesLanguageCorrection = true

let handler = VNImageRequestHandler(cgImage: cg, options: [:])
try? handler.perform([request])
