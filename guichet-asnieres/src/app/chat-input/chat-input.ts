import { Component, input, signal, output } from '@angular/core';

interface Suggestion {
  title: string;
  subtitle: string;
  prompt: string;
  icon: 'id' | 'school' | 'clock' | 'doc';
}

@Component({
  selector: 'app-chat-input',
  imports: [],
  templateUrl: './chat-input.html'
})
export class ChatInputComponent {
  conversationStarted = input(false);
  prompt = signal('');
  submitted = output<string>();

  suggestions: Suggestion[] = [
    {
      title: 'Passeport & Carte d’identité',
      subtitle: 'Pièces requises, pré-demande & RDV',
      prompt: 'Quels sont les documents nécessaires pour refaire mon passeport ou ma carte d’identité ?',
      icon: 'id'
    },
    {
      title: 'Inscriptions scolaires & Cantine',
      subtitle: 'Quotient familial et restauration',
      prompt: 'Comment inscrire mon enfant à l’école et à la cantine municipale ?',
      icon: 'school'
    },
    {
      title: 'Horaires & Accès Mairie',
      subtitle: 'Hôtel de Ville et mairies de quartier',
      prompt: 'Quels sont les horaires d’ouverture de l’Hôtel de Ville d’Asnières ?',
      icon: 'clock'
    },
    {
      title: 'Actes d’état civil',
      subtitle: 'Naissance, mariage, livret de famille',
      prompt: 'Comment obtenir un acte de naissance ou de mariage en ligne ?',
      icon: 'doc'
    }
  ];

  onInput(event: Event) {
    const value = (event.target as HTMLTextAreaElement).value;
    this.prompt.set(value);
  }

  onKeyDown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  selectSuggestion(suggestionPrompt: string) {
    this.prompt.set(suggestionPrompt);
  }

  send() {
    const val = this.prompt().trim();
    if (val) {
      this.submitted.emit(val);
      this.prompt.set('');
    }
  }
}