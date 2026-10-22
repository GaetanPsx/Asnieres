import { Component, signal } from '@angular/core';
import { Navbar } from './navbar/navbar';
import { ChatInputComponent } from './chat-input/chat-input';


@Component({
  selector: 'app-root',
  imports: [Navbar, ChatInputComponent],
  template: `
    <div class="h-dvh min-h-[32rem] bg-slate-50 flex flex-col overflow-hidden">
      <app-navbar />
      @if (messages().length === 0) {
        <main class="flex-1 flex items-center justify-center px-4 py-10 sm:px-8 lg:px-12">
          <app-chat-input class="w-full" (submitted)="handlePrompt($event)" />
        </main>
      } @else {
        <main class="flex-1 min-h-0 flex flex-col px-4 sm:px-8 lg:px-12">
          <div class="w-full max-w-5xl mx-auto pt-4">
            <button
              type="button"
              (click)="returnToHome()"
              class="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-200 hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
              </svg>
              Retour à l'accueil
            </button>
          </div>
          <div class="flex-1 min-h-0 w-full max-w-5xl mx-auto overflow-y-auto py-8 space-y-6" aria-live="polite">
            @for (message of messages(); track $index) {
              @if (message.role === 'user') {
                <div class="flex justify-end">
                  <div class="max-w-[85%] sm:max-w-[75%] rounded-2xl rounded-br-md bg-blue-700 px-5 py-3.5 text-white shadow-sm">
                    <p class="whitespace-pre-wrap break-words">{{ message.content }}</p>
                  </div>
                </div>
              } @else {
                <div class="flex items-start gap-3">
                  <div class="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-100 text-blue-700" aria-hidden="true">
                    <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 3l1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3z"/>
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M19 14l1.1 2.9L23 18l-2.9 1.1L19 22l-1.1-2.9L15 18l2.9-1.1L19 14z"/>
                    </svg>
                  </div>
                  <div class="max-w-[85%] sm:max-w-[75%] rounded-2xl rounded-tl-md border border-slate-200 bg-white px-5 py-3.5 text-slate-600 shadow-sm">
                    <p class="whitespace-pre-wrap">{{ message.content }}</p>
                  </div>
                </div>
              }
            }
          </div>
          <div class="w-full shrink-0 border-t border-slate-200 bg-slate-50 py-4">
            <app-chat-input class="w-full" [conversationStarted]="true" (submitted)="handlePrompt($event)" />
          </div>
        </main>
      }
    </div>
  `
})
export class App {
  messages = signal<{ role: 'user' | 'assistant'; content: string }[]>([]);

  handlePrompt(text: string) {
    this.messages.update((messages) => [
      ...messages,
      { role: 'user', content: text },
      {
        role: 'assistant',
        content: "La réponse à votre question s'affichera ici lorsque le service de réponse sera connecté."
      }
    ]);
  }

  returnToHome() {
    this.messages.set([]);
  }
}
