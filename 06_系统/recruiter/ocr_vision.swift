import Foundation
import ImageIO
import Vision

func recognize(_ path: String) throws -> String {
    let url = URL(fileURLWithPath: path) as CFURL
    guard let source = CGImageSourceCreateWithURL(url, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        throw NSError(domain: "CodexRecruiterOCR", code: 1, userInfo: [NSLocalizedDescriptionKey: "无法读取图片：\(path)"])
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["zh-Hans", "en-US"]
    request.usesLanguageCorrection = true
    let handler = VNImageRequestHandler(cgImage: image, options: [:])
    try handler.perform([request])

    let observations = (request.results ?? []).sorted { left, right in
        let verticalDifference = abs(left.boundingBox.midY - right.boundingBox.midY)
        if verticalDifference > 0.012 {
            return left.boundingBox.midY > right.boundingBox.midY
        }
        return left.boundingBox.minX < right.boundingBox.minX
    }
    return observations.compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n")
}

var output: [String: String] = [:]
do {
    for path in CommandLine.arguments.dropFirst() {
        output[path] = try recognize(path)
    }
    let data = try JSONSerialization.data(withJSONObject: output, options: [])
    FileHandle.standardOutput.write(data)
} catch {
    FileHandle.standardError.write(Data(error.localizedDescription.utf8))
    exit(1)
}
