import { Component , inject, OnInit} from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';
import { Api } from './api';

@Component({
  imports: [RouterOutlet],
  selector: 'app-root',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})

export class App implements OnInit {
  api = inject(Api);
  private router = inject(Router);

  ngOnInit() {
    this.api.status().subscribe(s => this.api.running.set(s.running));
    this.api.settings().subscribe(s => {
      if (!s.configured && this.router.url !== '/settings') {
        this.router.navigate(['/settings']);
      }
    });
  }
}
