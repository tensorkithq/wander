//
//  ContentView.swift
//  wander Watch App
//

import SwiftUI

/// One screen, one button. Press-and-hold to record a wrist gesture, release to
/// cast. A `DragGesture(minimumDistance: 0)` is the standard SwiftUI way to get
/// press (`onChanged`) + release (`onEnded`) on watchOS.
struct ContentView: View {
    @StateObject private var caster = WandCaster()

    private var isCasting: Bool { caster.phase == .casting }

    var body: some View {
        VStack(spacing: 8) {
            Text(statusText)
                .font(.headline)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.7)

            castButton

            Text(subText)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(.horizontal, 6)
    }

    private var castButton: some View {
        ZStack {
            Circle()
                .fill(isCasting ? Color.blue : Color.indigo)
                .overlay(Circle().stroke(.white.opacity(0.25), lineWidth: 2))
                .shadow(color: isCasting ? .blue.opacity(0.6) : .clear, radius: 12)
            Text(isCasting ? "✦" : "Cast")
                .font(.title2).bold()
                .foregroundStyle(.white)
        }
        .frame(width: 108, height: 108)
        .scaleEffect(isCasting ? 0.93 : 1)
        .animation(.easeOut(duration: 0.12), value: isCasting)
        .gesture(
            DragGesture(minimumDistance: 0)
                .onChanged { _ in caster.startCast() }
                .onEnded { _ in caster.endCast() }
        )
        .accessibilityLabel("Cast a spell — hold and flick your wrist")
    }

    private var statusText: String {
        switch caster.phase {
        case .idle:            return "Wander"
        case .casting:         return "Casting…"
        case .sending:         return "Sending…"
        case .result(let s):   return s
        case .failed(let e):   return "⚠️ \(e)"
        }
    }

    private var subText: String {
        switch caster.phase {
        case .casting:  return "\(caster.sampleCount) samples"
        case .sending:  return "to Yugo"
        case .result:   return "hold to cast again"
        default:        return "hold & flick"
        }
    }
}

#Preview {
    ContentView()
}
