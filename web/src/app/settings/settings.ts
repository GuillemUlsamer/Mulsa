import { Component, inject, signal, OnInit, OnDestroy } from '@angular/core';
import { Subscription } from 'rxjs';
import { Router, RouterLink} from '@angular/router';
import { Api } from '../api';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { Page } from '../page/page';

@Component({
  imports: [ReactiveFormsModule, RouterLink, Page],
  selector: 'app-settings',
  styleUrl: './settings.scss',
  templateUrl: './settings.html',
})
export class Settings implements OnInit, OnDestroy {
  private api = inject(Api);
  private router = inject(Router);
  private fb = inject(FormBuilder);

  form = this.fb.nonNullable.group({
    soulseek_username: '',
    soulseek_password: '',
    music_dir: '',
    share_dir: '',
    credentials_file: '',
    listen_port: 50300,
    // discogs_token: '',
  });

  status = signal('');
  saving = signal(false);
  google = signal(false);
  configured = signal(false);
  advanced = signal(false);
  mascot = signal(true);
  error = signal(false);
  private sub?: Subscription;

  ngOnInit() {
    this.api.settings().subscribe(s => { this.form.patchValue(s); this.configured.set(s.configured); });
    this.refreshGoogle();
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
  }

  refreshGoogle() {
    this.api.googleStatus().subscribe(s => this.google.set(s.connected));
  }

  // El login acaba en el navegador, fuera de la app: nos enteramos por el evento de log.
  googleLogin() {
    this.status.set('Waiting for the browser...');
    this.api.googleLogin().subscribe();
    this.sub?.unsubscribe();
    this.sub = this.api.events().subscribe(e => {
      if (e.kind !== 'line' || !e.text.startsWith('Google')) return;
      this.status.set(e.text);
      this.refreshGoogle();
      this.sub?.unsubscribe();
    });
  }

  googleLogout() {
    this.api.googleLogout().subscribe(() => { this.google.set(false); this.status.set(''); });
  }

  save() {
    this.saving.set(true);
    this.error.set(false);
    this.status.set('Setting up...');
    this.api.saveSettings(this.form.getRawValue()).subscribe({
      next: () => this.router.navigateByUrl('/'),
      error: e => { 
        this.saving.set(false); 
        this.error.set(true);
        this.status.set(e.error?.detail ?? 'Error'); 
      },
    });
  }

  browse(field: 'music_dir' | 'share_dir' | 'credentials_file') {
    let req;
    if (field === 'music_dir' || field === 'share_dir') {
      req = this.api.pickFolder();
    } else {
      req = this.api.pickFile();
    }
    req.subscribe(r => {
      if (r.path) this.form.patchValue({ [field]: r.path });
    });
  }
}
